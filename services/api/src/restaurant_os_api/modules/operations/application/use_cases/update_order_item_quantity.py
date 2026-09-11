"""UpdateOrderItemQuantityUseCase.

Line-level quantity edit, sibling to ``VoidOrderItemUseCase`` -- same
flat route shape (``PATCH /api/v1/orders/{order_id}/items/{order_item_id}``),
same coarse/fine ``order.manage`` authorization split every other flat
Operations route in this module already follows.

Delegates the precondition to ``OrderItem.change_quantity()`` -- pre-fire
only (``added`` line status), the identical boundary
``VoidOrderItemUseCase`` already established: a line already sent to the
kitchen has no route here to silently change what's cooking. Reducing a
fired line's quantity is out of scope here the same way voiding one is
out of scope for ``VoidOrderItemUseCase`` -- a future "86 N of these"
workflow, not built by this step.

Built specifically so a counter POS screen's quantity +/- mutates one
line in place rather than creating a second line for the same menu item.
``AddOrderItemUseCase`` always inserts a brand-new ``OrderItem`` row
(``add_order_item.py``'s own code, not just its docstring) -- tapping
the same tile three times before this endpoint existed produced three
separate rows at quantity 1 each, not one row at quantity 3.
``bill-print-view.tsx`` prints one ``<tr>`` per ``OrderItem`` with no
menu-item-level merging, so those three rows would print as three
separate ₹90.00 lines rather than one ``3 x ₹90.00 = ₹270.00`` line --
a customer-facing printed-receipt defect, not just an internal
bookkeeping inconvenience a merged UI could paper over. This endpoint
exists so the POS screen never creates that duplicate-line shape in the
first place.

Adjusts ``Order.subtotal_amount`` by the exact delta between the old and
new quantity (not a full recompute), the same incremental-accounting
shape ``AddOrderItemUseCase``/``VoidOrderItemUseCase`` already use.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import (
    OrderDTO,
    UpdateOrderItemQuantityRequestDTO,
)
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


class UpdateOrderItemQuantityUseCase:
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
        self, tenant_id: str, user_id: str, request: UpdateOrderItemQuantityRequestDTO
    ) -> OrderDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            order = await order_repo.get_by_id(tenant_id, request.order_id)
            if order is None:
                raise OrderNotFoundError(request.order_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=order.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            item = await order_repo.get_item_by_id(tenant_id, request.order_item_id)
            if item is None or item.order_id != order.id:
                raise OrderItemNotFoundError(request.order_item_id)

            previous_quantity = item.quantity
            item.change_quantity(request.quantity)
            await order_repo.update_item(item)

            order.subtotal_amount = order.subtotal_amount + (
                item.unit_price_amount * (item.quantity - previous_quantity)
            )
            order = await order_repo.update(order)

            items = await order_repo.get_items(tenant_id, order.id)

        return order_to_dto(order, items)
