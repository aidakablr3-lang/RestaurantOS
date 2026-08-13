"""GuestResolveQRCodeUseCase.

Every guest-ordering route (``/api/v1/qr/{token}/menu``,
``/orders``, ``/orders/{order_id}/items``, ``/submit``,
``/orders/{order_id}``) re-resolves the token on *every* call -- the
guest flow's whole authorization model (see
``operations.application.use_cases._guest_order_guard``'s own
docstring). Deliberately **not** ``ResolveQRCodeUseCase`` reused
directly: that use case's ``QRResolutionRateLimiter`` quotas
(``IP_TOTAL_LIMIT=30``/``TOKEN_TOTAL_LIMIT=20`` per 60s) were sized for
a single bootstrap lookup, not for every step of an ordering session
(menu load, create order, several add-item calls, submit, a few status
polls easily clears 8-10 calls) -- reusing it here would silently burn
through the resolution endpoint's own abuse budget for unrelated
traffic, and one busy table's restaurant-wifi-shared IP could exhaust it
for every other table's *first* QR scan. Uses ``GuestOrderRateLimiter``
instead (its own ``"order:"``-namespaced counters on the same table, see
that limiter's own docstring) and skips ``record_failure`` entirely --
this limiter tracks no separate failed-count.

Same enumeration protection as ``ResolveQRCodeUseCase``: "does not
exist" and "exists but revoked" both collapse into a plain ``None``.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import QRCodeResolutionDTO
from restaurant_os_api.modules.restaurant.domain.entities import QRCodeStatus
from restaurant_os_api.modules.restaurant.domain.ports import QRCodeRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.rate_limiting import GuestOrderRateLimiter


class GuestResolveQRCodeUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        qr_code_repository_factory: Callable[[AsyncSession], QRCodeRepository],
        rate_limiter: GuestOrderRateLimiter,
    ) -> None:
        self._session_factory = session_factory
        self._qr_code_repository_factory = qr_code_repository_factory
        self._rate_limiter = rate_limiter

    async def execute(self, token: str, source_ip: str) -> QRCodeResolutionDTO | None:
        await self._rate_limiter.check(source_ip=source_ip, token=token)

        async with UnitOfWork(self._session_factory) as uow:
            qr_code_repo = self._qr_code_repository_factory(uow.session)
            qr_code = await qr_code_repo.get_by_token(token)

        if qr_code is None or qr_code.status != QRCodeStatus.ACTIVE:
            return None

        return QRCodeResolutionDTO(
            tenant_id=qr_code.tenant_id, branch_id=qr_code.branch_id, table_id=qr_code.table_id
        )
