"""AddPurchaseOrderItemUseCase.

Flat ``POST /api/v1/purchase-orders/{id}/items`` -- same coarse/fine
authorization split as ``AddOrderItemUseCase``. Only legal while the
PurchaseOrder is still ``draft`` (Architecture doc SS3.7: items are
added before sending). ``inventory_item_id`` is verified to exist
within the tenant (not necessarily the same branch as the PO -- see
``revise_recipe.py``'s own disclosed Recipe/InventoryItem tension for
the identical, inherited modeling gap; a purchase order line
referencing an ingredient from a different branch's stock isn't
validated further here).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import (
    AddPurchaseOrderItemRequestDTO,
    PurchaseOrderDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._purchase_order_mapper import (
    purchase_order_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import (
    PurchaseOrderItem,
    PurchaseOrderStatus,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidPurchaseOrderStatusTransitionError,
    InventoryItemNotFoundError,
    PurchaseOrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryItemRepository,
    PurchaseOrderRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "purchasing.manage"


class AddPurchaseOrderItemUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        purchase_order_repository_factory: Callable[[AsyncSession], PurchaseOrderRepository],
        inventory_item_repository_factory: Callable[[AsyncSession], InventoryItemRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._purchase_order_repository_factory = purchase_order_repository_factory
        self._inventory_item_repository_factory = inventory_item_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, request: AddPurchaseOrderItemRequestDTO
    ) -> PurchaseOrderDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            po_repo = self._purchase_order_repository_factory(uow.session)
            inventory_item_repo = self._inventory_item_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            purchase_order = await po_repo.get_by_id(tenant_id, request.purchase_order_id)
            if purchase_order is None:
                raise PurchaseOrderNotFoundError(request.purchase_order_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=purchase_order.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            if purchase_order.status != PurchaseOrderStatus.DRAFT:
                raise InvalidPurchaseOrderStatusTransitionError(
                    purchase_order.id, purchase_order.status.value, "item_added"
                )

            inventory_item = await inventory_item_repo.get_by_id(
                tenant_id, request.inventory_item_id
            )
            if inventory_item is None:
                raise InventoryItemNotFoundError(request.inventory_item_id)

            await po_repo.add_item(
                PurchaseOrderItem(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    purchase_order_id=purchase_order.id,
                    inventory_item_id=request.inventory_item_id,
                    quantity_ordered=request.quantity_ordered,
                    quantity_received=Decimal(0),
                    created_at=now,
                )
            )

            items = await po_repo.get_items(tenant_id, purchase_order.id)
        return purchase_order_to_dto(purchase_order, items)
