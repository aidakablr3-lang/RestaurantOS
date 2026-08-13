"""SendPurchaseOrderUseCase.

Flat ``POST /api/v1/purchase-orders/{id}/send`` -- same coarse/fine
split as ``FireOrderUseCase``. Requires at least one line item
(``PurchaseOrderHasNoItemsError`` otherwise), the same "don't send a
meaningless order" precedent ``OrderHasNoItemsError`` established for
firing an empty order.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import PurchaseOrderDTO
from restaurant_os_api.modules.operations.application.use_cases._purchase_order_mapper import (
    purchase_order_to_dto,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    PurchaseOrderHasNoItemsError,
    PurchaseOrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import PurchaseOrderRepository
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "purchasing.manage"


class SendPurchaseOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        purchase_order_repository_factory: Callable[[AsyncSession], PurchaseOrderRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._purchase_order_repository_factory = purchase_order_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, purchase_order_id: str
    ) -> PurchaseOrderDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            po_repo = self._purchase_order_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            purchase_order = await po_repo.get_by_id(tenant_id, purchase_order_id)
            if purchase_order is None:
                raise PurchaseOrderNotFoundError(purchase_order_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=purchase_order.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            items = await po_repo.get_items(tenant_id, purchase_order_id)
            if not items:
                raise PurchaseOrderHasNoItemsError(purchase_order_id)

            purchase_order.send()
            purchase_order = await po_repo.update(purchase_order)
        return purchase_order_to_dto(purchase_order, items)
