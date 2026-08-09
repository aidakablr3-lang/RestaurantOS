"""QRResolutionRateLimiter -- ADR 0001's Postgres-backed rate limiting
for ``GET /api/v1/qr/{token}`` (Sprint 5 Step 4.7, the Step 4 Decision
Lock's Decision 6: Postgres, not Redis).

Fixed-window counters, one row per ``(bucket_type, bucket_key,
window_start)``, incremented via a single atomic
``INSERT ... ON CONFLICT DO UPDATE ... RETURNING`` -- the same
``pg_insert(...).on_conflict_do_update(...)`` construct
``SQLAlchemySystemSettingRepository`` already uses elsewhere in this
codebase, applied here to an increment instead of an overwrite.
Concurrent requests against the same bucket in the same window
serialize on that row's own lock; the count returned by ``RETURNING``
is always the true post-increment value under concurrency, which is
what makes "N concurrent requests, only limit-many allowed" hold in
practice, not just when requests happen to arrive sequentially.

Two independent counters per row -- ``total_count`` (every attempt,
success or failure) and ``failed_count`` (only unresolvable attempts)
-- so a stricter limit can apply to failures (ADR 0001: "apply a
stricter limit to failed resolutions... than to successful ones")
without a third bucket dimension. ``check()`` increments ``total_count``
for both the IP and token buckets *before* the token lookup runs (so
an already-blocked IP never reaches the database for the lookup
itself); ``record_failure()`` increments ``failed_count`` for both
*after* the lookup determines the token did not resolve.

No tenant context: every DB access here uses ``UnitOfWork(session_factory)``
with no ``TenantContext``, the same precedented pattern
``GetTenantUseCase``/``ListTenantsUseCase``/``ListPermissionsUseCase``
already use for queries that must run before any tenant is known.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.rate_limiting.exceptions import RateLimitExceededError
from restaurant_os_api.platform.rate_limiting.models import RateLimitCounterModel

_WINDOW_SECONDS = 60

# ADR 0001 specifies the *mechanism* (per-IP, per-token, stricter for
# failures) but names no specific quotas. These are a deliberately
# conservative, disclosed default -- not read from anywhere else in
# the architecture -- chosen so a single table scanned by many
# legitimate guests in the same minute is not itself throttled, while
# a fast-guessing script against one IP or one token is.
_IP_TOTAL_LIMIT = 30
_IP_FAILED_LIMIT = 10
_TOKEN_TOTAL_LIMIT = 20
_TOKEN_FAILED_LIMIT = 5


def _window_start(now: datetime) -> datetime:
    epoch_seconds = int(now.timestamp())
    floored = (epoch_seconds // _WINDOW_SECONDS) * _WINDOW_SECONDS
    return datetime.fromtimestamp(floored, tz=UTC)


class QRResolutionRateLimiter:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def check(self, *, source_ip: str, token: str) -> None:
        window_start = _window_start(datetime.now(UTC))

        ip_total = await self._increment_total("ip", source_ip, window_start)
        if ip_total > _IP_TOTAL_LIMIT:
            raise RateLimitExceededError()

        token_total = await self._increment_total("token", token, window_start)
        if token_total > _TOKEN_TOTAL_LIMIT:
            raise RateLimitExceededError()

    async def record_failure(self, *, source_ip: str, token: str) -> None:
        window_start = _window_start(datetime.now(UTC))

        ip_failed = await self._increment_failed("ip", source_ip, window_start)
        if ip_failed > _IP_FAILED_LIMIT:
            raise RateLimitExceededError()

        token_failed = await self._increment_failed("token", token, window_start)
        if token_failed > _TOKEN_FAILED_LIMIT:
            raise RateLimitExceededError()

    async def _increment_total(
        self, bucket_type: str, bucket_key: str, window_start: datetime
    ) -> int:
        stmt = (
            pg_insert(RateLimitCounterModel)
            .values(
                id=generate_ulid(),
                bucket_type=bucket_type,
                bucket_key=bucket_key,
                window_start=window_start,
                total_count=1,
                failed_count=0,
            )
            .on_conflict_do_update(
                index_elements=["bucket_type", "bucket_key", "window_start"],
                set_={"total_count": RateLimitCounterModel.total_count + 1},
            )
            .returning(RateLimitCounterModel.total_count)
        )
        async with UnitOfWork(self._session_factory) as uow:
            result = await uow.session.execute(stmt)
            return result.scalar_one()

    async def _increment_failed(
        self, bucket_type: str, bucket_key: str, window_start: datetime
    ) -> int:
        # Inserts total_count=1 too, only used if this exact window's
        # row does not already exist (the rare case where the window
        # rolled over between `check()` and `record_failure()` for the
        # same request) -- keeps failed_count <= total_count true even
        # then. The far more common path is the conflict branch, which
        # only touches failed_count: `check()` already incremented
        # total_count for this window earlier in the same request.
        stmt = (
            pg_insert(RateLimitCounterModel)
            .values(
                id=generate_ulid(),
                bucket_type=bucket_type,
                bucket_key=bucket_key,
                window_start=window_start,
                total_count=1,
                failed_count=1,
            )
            .on_conflict_do_update(
                index_elements=["bucket_type", "bucket_key", "window_start"],
                set_={"failed_count": RateLimitCounterModel.failed_count + 1},
            )
            .returning(RateLimitCounterModel.failed_count)
        )
        async with UnitOfWork(self._session_factory) as uow:
            result = await uow.session.execute(stmt)
            return result.scalar_one()
