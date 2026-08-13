"""CreatePurchaseOrderUseCase.

``POST /api/v1/branches/{branch_id}/purchase-orders`` -- branch-nested,
mirrors ``CreateOrderUseCase``'s own shape: created empty (``draft``,
no items), items are added afterward via
``AddPurchaseOrderItemUseCase`` (a separate flat call), the same
two-step create-then-add-items pattern ``Order``/``OrderItem`` already
established.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import (
    CreatePurchaseOrderRequestDTO,
    PurchaseOrderDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._purchase_order_mapper import (
    purchase_order_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import PurchaseOrder, PurchaseOrderStatus
from restaurant_os_api.modules.operations.domain.exceptions import SupplierNotFoundError
from restaurant_os_api.modules.operations.domain.ports import (
    PurchaseOrderRepository,
    SupplierRepository,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class CreatePurchaseOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        purchase_order_repository_factory: Callable[[AsyncSession], PurchaseOrderRepository],
        supplier_repository_factory: Callable[[AsyncSession], SupplierRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
    ) -> None:
        self._session_factory = session_factory
        self._purchase_order_repository_factory = purchase_order_repository_factory
        self._supplier_repository_factory = supplier_repository_factory
        self._branch_repository_factory = branch_repository_factory

    async def execute(
        self, tenant_id: str, request: CreatePurchaseOrderRequestDTO
    ) -> PurchaseOrderDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            supplier_repo = self._supplier_repository_factory(uow.session)
            po_repo = self._purchase_order_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            supplier = await supplier_repo.get_by_id(tenant_id, request.supplier_id)
            if supplier is None:
                raise SupplierNotFoundError(request.supplier_id)

            purchase_order = await po_repo.create(
                PurchaseOrder(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    supplier_id=request.supplier_id,
                    status=PurchaseOrderStatus.DRAFT,
                    created_at=now,
                )
            )
        return purchase_order_to_dto(purchase_order, [])
