"""GetPurchaseOrderUseCase."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import PurchaseOrderDTO
from restaurant_os_api.modules.operations.application.use_cases._purchase_order_mapper import (
    purchase_order_to_dto,
)
from restaurant_os_api.modules.operations.domain.exceptions import PurchaseOrderNotFoundError
from restaurant_os_api.modules.operations.domain.ports import PurchaseOrderRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetPurchaseOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        purchase_order_repository_factory: Callable[[AsyncSession], PurchaseOrderRepository],
    ) -> None:
        self._session_factory = session_factory
        self._purchase_order_repository_factory = purchase_order_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, purchase_order_id: str
    ) -> PurchaseOrderDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            po_repo = self._purchase_order_repository_factory(uow.session)
            purchase_order = await po_repo.get_by_id(tenant_id, purchase_order_id)
            if purchase_order is None or purchase_order.branch_id != branch_id:
                raise PurchaseOrderNotFoundError(purchase_order_id)
            items = await po_repo.get_items(tenant_id, purchase_order_id)
        return purchase_order_to_dto(purchase_order, items)
