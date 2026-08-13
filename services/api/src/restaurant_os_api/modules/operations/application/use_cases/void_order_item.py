"""VoidOrderItemUseCase.

Line-level counterpart to ``VoidOrderUseCase``: voids a single
``OrderItem`` rather than the whole order. A flat route (``POST
/api/v1/orders/{order_id}/items/{order_item_id}/void``, not nested
under ``branch_id`` -- same reasoning as ``AddOrderItemUseCase``), the
same coarse/fine-grained ``order.manage`` split every other flat
Operations route in this module already follows.

Delegates the precondition entirely to ``OrderItem.void()`` -- pre-fire
only (``added -> voided``; Architecture doc SS3.1: "voidable pre-fire
only"). A caller who needs to remove a line that has already been sent
to the kitchen has no route here -- that is ``VoidOrderUseCase``
territory (void the whole order) or a future "86 this fired item and
tell the kitchen" workflow, real scope this step doesn't take on,
mirroring the same disclosed gap ``void_order.py`` already documents
for post-fire whole-order voids.

Backs the voided line's cost out of ``Order.subtotal_amount`` --
the exact inverse of the accumulation ``AddOrderItemUseCase`` performs
when the line was added, so a voided-then-never-refired line never
lingers in the order's own total.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import OrderDTO
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.domain.exceptions import (
    OrderItemNotFoundError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import OrderRepository
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "order.manage"


class VoidOrderItemUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, order_id: str, order_item_id: str
    ) -> OrderDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            order = await order_repo.get_by_id(tenant_id, order_id)
            if order is None:
                raise OrderNotFoundError(order_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=order.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            item = await order_repo.get_item_by_id(tenant_id, order_item_id)
            if item is None or item.order_id != order.id:
                raise OrderItemNotFoundError(order_item_id)

            item.void()
            await order_repo.update_item(item)

            order.subtotal_amount = order.subtotal_amount - (item.unit_price_amount * item.quantity)
            order = await order_repo.update(order)

            items = await order_repo.get_items(tenant_id, order.id)

        return order_to_dto(order, items)
