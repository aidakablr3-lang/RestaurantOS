"""GuestGetOrderUseCase.

Backs ``GET /api/v1/qr/{token}/orders/{order_id}`` (guest ordering) --
lets a guest poll their own order's status (item lines, kitchen
progress via ``line_status``, running total) without a staff login.
Deliberately not just the staff ``GetOrderUseCase`` reused directly:
that use case only checks ``branch_id``, and a guest's QR token also
proves *which table*, so this adds the same ``table_id`` check
``ensure_guest_order_access`` already enforces for the guest write
paths -- a guest at table 5 gets a 404 (not a 403 -- no existence leak)
polling an order that belongs to table 3, the same as they would trying
to add an item to it.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import OrderDTO
from restaurant_os_api.modules.operations.application.use_cases._guest_order_guard import (
    ensure_guest_order_access,
)
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.domain.exceptions import OrderNotFoundError
from restaurant_os_api.modules.operations.domain.ports import OrderRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GuestGetOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, table_id: str, order_id: str
    ) -> OrderDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            order = await order_repo.get_by_id(tenant_id, order_id)
            if order is None:
                raise OrderNotFoundError(order_id)
            ensure_guest_order_access(order, branch_id=branch_id, table_id=table_id)
            items = await order_repo.get_items(tenant_id, order_id)
        return order_to_dto(order, items)
