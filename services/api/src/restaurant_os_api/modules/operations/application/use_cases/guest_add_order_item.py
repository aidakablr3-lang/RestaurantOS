"""GuestAddOrderItemUseCase.

Backs ``POST /api/v1/qr/{token}/orders/{order_id}/items`` (guest
ordering). Same rules as the staff-facing ``AddOrderItemUseCase`` --
legal while the order is ``OPEN`` or already ``FIRED``, ``menu_item_id``
must belong to the order branch's own restaurant and be available, price
is snapshotted from ``MenuItem.price_amount`` (same disclosed
branch-price/availability-override gap) -- but takes no ``user_id`` and
does no RBAC resolution: the caller has already proven table-presence by
holding a QR token the router just re-resolved, and
``ensure_guest_order_access`` re-checks the loaded order's
``branch_id``/``table_id`` against that resolution before anything else,
the guest-flow's own authorization model in place of
``resolve_and_authorize_branch``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import (
    AddOrderItemRequestDTO,
    OrderDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._guest_order_guard import (
    ensure_guest_order_access,
)
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.domain.entities import (
    OrderItem,
    OrderItemLineStatus,
    OrderStatus,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidOrderStatusTransitionError,
    MenuItemNotAvailableError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import OrderRepository
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    MenuItemNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    MenuCategoryRepository,
    MenuItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GuestAddOrderItemUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._menu_category_repository_factory = menu_category_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, table_id: str, request: AddOrderItemRequestDTO
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
            ensure_guest_order_access(order, branch_id=branch_id, table_id=table_id)

            if order.status not in (OrderStatus.OPEN, OrderStatus.FIRED):
                raise InvalidOrderStatusTransitionError(order.id, order.status.value, "item_added")

            branch = await branch_repo.get_by_id(tenant_id, branch_id)
            if branch is None:
                raise BranchNotFoundError(branch_id)

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
