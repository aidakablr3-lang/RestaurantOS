"""AddOrderItemUseCase.

A flat route (``POST /api/v1/orders/{order_id}/items``, not nested
under ``branch_id`` -- the order itself already carries its own branch
context) -- gated the same "coarse router gate, fine-grained use-case
decision" way ``ChangeTableStatusUseCase`` established: the router
checks ``order.manage`` at any scope, this use case resolves the
order's real ``branch_id`` and re-checks the caller's grants against
that specific branch via ``resolve_and_authorize_branch`` (reused
directly from the restaurant module -- the same ``branches`` table,
the same shape of check, no reason to duplicate it).

Only legal while the order is still ``OPEN`` (Architecture doc SS3.1:
line items are added before firing). ``menu_item_id`` is verified to
belong to the *same restaurant* as the order's own branch (via
``MenuCategory.restaurant_id`` -- ``MenuItem`` itself carries no
``restaurant_id`` column, only ``menu_category_id``) -- a menu item
belonging to an unrelated restaurant is the same cross-scope-is-404
discipline as everywhere else, raising the restaurant module's own
``MenuItemNotFoundError`` (reused as-is; Operations doesn't own
``MenuItem``). A menu item that exists, belongs to the right
restaurant, but has ``is_available = false`` raises this module's own
``MenuItemNotAvailableError`` instead -- a genuinely different failure
mode.

``unit_price_amount`` is snapshotted from ``MenuItem.price_amount``
directly -- branch-price overrides (``MenuItemBranchPrice``) and
time-windowed availability overrides (``MenuItemAvailability``) are
**not** resolved here. A disclosed scope-narrowing: the full
"what's the effective price/availability for this item at this branch
right now" resolution is real, separate logic (nothing in the codebase
provides it as a reusable helper yet) that a future step should add,
not something worth building ad hoc inside this use case.

Accumulates the new line's cost into ``Order.subtotal_amount``.
Publishes no event of its own yet -- ``OrderItemAdded`` was considered
but cut: nothing in this step consumes it, and an unconsumed event is
speculative surface, not evidence of correctness.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import (
    AddOrderItemRequestDTO,
    OrderDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.domain.entities import OrderItem, OrderItemLineStatus
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidOrderStatusTransitionError,
    MenuItemNotAvailableError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import OrderRepository
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    MenuCategoryRepository,
    MenuItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "order.manage"


class AddOrderItemUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._menu_category_repository_factory = menu_category_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, request: AddOrderItemRequestDTO
    ) -> OrderDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            menu_category_repo = self._menu_category_repository_factory(uow.session)

            order = await order_repo.get_by_id(tenant_id, request.order_id)
            if order is None:
                raise OrderNotFoundError(request.order_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            branch = await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=order.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            if order.status != order.status.OPEN:
                raise InvalidOrderStatusTransitionError(order.id, order.status.value, "item_added")

            menu_item = await menu_item_repo.get_by_id(tenant_id, request.menu_item_id)
            if menu_item is None:
                raise MenuItemNotFoundError(request.menu_item_id)

            menu_category = await menu_category_repo.get_by_id(
                tenant_id, menu_item.menu_category_id
            )
            if menu_category is None or menu_category.restaurant_id != branch.restaurant_id:
                raise MenuItemNotFoundError(request.menu_item_id)

            if not menu_item.is_available:
                raise MenuItemNotAvailableError(request.menu_item_id)

            item = await order_repo.add_item(
                OrderItem(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    order_id=order.id,
                    menu_item_id=menu_item.id,
                    quantity=request.quantity,
                    unit_price_amount=menu_item.price_amount,
                    line_status=OrderItemLineStatus.ADDED,
                    created_at=now,
                    modifiers_snapshot=request.modifiers_snapshot,
                )
            )

            order.subtotal_amount = order.subtotal_amount + (item.unit_price_amount * item.quantity)
            order = await order_repo.update(order)

            items = await order_repo.get_items(tenant_id, order.id)

        return order_to_dto(order, items)
