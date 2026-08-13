"""GuestOrderRateLimiter -- rate limiting for the guest QR ordering
write paths (``POST /api/v1/qr/{token}/orders...``), reusing
``QRResolutionRateLimiter``'s own table (``qr_resolution_rate_limits``)
and fixed-window mechanism rather than standing up a second one.

No migration: the table's ``bucket_type`` CHECK constraint already
allows exactly ``('ip', 'token')``, and this limiter uses those same two
values -- an ``"order:"`` prefix on ``bucket_key`` is what keeps a
guest's ordering activity in its own counters, separate from QR
*resolution* attempts against the same IP/token (``QRResolutionRateLimiter``
already owns that ``bucket_key`` namespace unprefixed).

Looser quotas than QR resolution -- a legitimate guest session is
several real writes (create order, a few add-item calls, submit, a
handful of status polls), not a single lookup, so the limit has to
comfortably cover that without also being generous enough to enable
order-flooding abuse. No separate "failed" counter: unlike QR
resolution's not-found/revoked signal, an order-write failure (e.g. an
unavailable menu item) is an ordinary domain outcome, not evidence of
scanning -- there's no failure signal here worth bucketing separately.
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
_IP_LIMIT = 60
_TOKEN_LIMIT = 40


def _window_start(now: datetime) -> datetime:
    epoch_seconds = int(now.timestamp())
    floored = (epoch_seconds // _WINDOW_SECONDS) * _WINDOW_SECONDS
    return datetime.fromtimestamp(floored, tz=UTC)


class GuestOrderRateLimiter:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def check(self, *, source_ip: str, token: str) -> None:
        window_start = _window_start(datetime.now(UTC))

        ip_total = await self._increment("ip", f"order:{source_ip}", window_start)
        if ip_total > _IP_LIMIT:
            raise RateLimitExceededError()

        token_total = await self._increment("token", f"order:{token}", window_start)
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
