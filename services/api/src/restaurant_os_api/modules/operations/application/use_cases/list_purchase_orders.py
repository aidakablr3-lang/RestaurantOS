"""ListPurchaseOrdersUseCase."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import PurchaseOrderListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._purchase_order_mapper import (
    purchase_order_to_dto,
)
from restaurant_os_api.modules.operations.domain.ports import PurchaseOrderRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListPurchaseOrdersUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        purchase_order_repository_factory: Callable[[AsyncSession], PurchaseOrderRepository],
    ) -> None:
        self._session_factory = session_factory
        self._purchase_order_repository_factory = purchase_order_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> PurchaseOrderListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            po_repo = self._purchase_order_repository_factory(uow.session)
            purchase_orders, total = await po_repo.list_for_branch(
                tenant_id, branch_id, offset=offset, limit=limit
            )
            # List view omits items, matching ListOrdersUseCase's own
            # precedent -- GetPurchaseOrderUseCase is the detail path.
            dtos = [purchase_order_to_dto(po, []) for po in purchase_orders]
        return PurchaseOrderListResultDTO(
            purchase_orders=dtos, total=total, offset=offset, limit=limit
        )
