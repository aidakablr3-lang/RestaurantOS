"""OwnerActivationRateLimiter -- rate limiting for
``POST /api/v1/owner-activation``, reusing ``QRResolutionRateLimiter``'s
own table (``qr_resolution_rate_limits``) and fixed-window mechanism
rather than standing up a second one -- the same reuse
``GuestOrderRateLimiter`` already established for guest ordering.

No migration: the table's ``bucket_type`` CHECK constraint already
allows exactly ``('ip', 'token')``, and this limiter uses those same two
values -- an ``"activation:"`` prefix on ``bucket_key`` keeps this
endpoint's attempts in their own counters, separate from QR resolution
and guest-order-write activity on the same table (``QRResolutionRateLimiter``
owns the unprefixed namespace, ``GuestOrderRateLimiter`` owns ``order:``).

This is exactly the endpoint Phase 1 design doc SSA.4's amendment calls
out: unauthenticated, and the token *is* the credential -- a scanning
client trying activation tokens must be rate-limited the same way a
client trying QR tokens already is.
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
_IP_LIMIT = 20
_TOKEN_LIMIT = 10


def _window_start(now: datetime) -> datetime:
    epoch_seconds = int(now.timestamp())
    floored = (epoch_seconds // _WINDOW_SECONDS) * _WINDOW_SECONDS
    return datetime.fromtimestamp(floored, tz=UTC)


class OwnerActivationRateLimiter:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def check(self, *, source_ip: str, token: str) -> None:
        window_start = _window_start(datetime.now(UTC))

        ip_total = await self._increment("ip", f"activation:{source_ip}", window_start)
        if ip_total > _IP_LIMIT:
            raise RateLimitExceededError()

        token_total = await self._increment("token", f"activation:{token}", window_start)
        if token_total > _TOKEN_LIMIT:
            raise RateLimitExceededError()

    async def _increment(self, bucket_type: str, bucket_key: str, window_start: datetime) -> int:
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
