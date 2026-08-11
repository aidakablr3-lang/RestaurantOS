"""Unit tests for Order CRUD + lifecycle use cases (Sprint 7 Step 3) --
in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import (
    AddOrderItemRequestDTO,
    CreateOrderRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    AddOrderItemUseCase,
    CloseOrderUseCase,
    CreateOrderUseCase,
    FireOrderUseCase,
    GetOrderUseCase,
    ListOrdersUseCase,
    VoidOrderUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import (
    Order,
    OrderItem,
    OrderItemLineStatus,
    OrderSource,
    OrderStatus,
)
from restaurant_os_api.modules.operations.domain.events import (
    OrderClosed,
    OrderFired,
    OrderPlaced,
    OrderVoided,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidOrderStatusTransitionError,
    MenuItemNotAvailableError,
    OrderHasNoItemsError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    MenuCategory,
    MenuItem,
    Restaurant,
    RestaurantStatus,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    MenuItemNotFoundError,
)
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    FakeResolveUserPermissionsUseCase,
    InMemoryKitchenTicketRepository,
    InMemoryOrderRepository,
    InMemoryTabRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import (
    InMemoryBranchRepository,
    InMemoryMenuCategoryRepository,
    InMemoryMenuItemRepository,
    InMemoryRestaurantRepository,
    InMemoryTableRepository,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
OTHER_RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX2"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT01"
OTHER_MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT02"
MENU_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6MITM01"
ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR01"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _restaurant(**overrides) -> Restaurant:
    defaults = {
        "id": RESTAURANT_ID,
        "tenant_id": TENANT_ID,
        "legal_name": "Test Restaurant LLC",
        "display_name": "Test Restaurant",
        "default_currency_code": "USD",
        "status": RestaurantStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Restaurant(**defaults)


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _menu_category(**overrides) -> MenuCategory:
    defaults = {
        "id": MENU_CATEGORY_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Mains",
        "display_order": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return MenuCategory(**defaults)


def _menu_item(**overrides) -> MenuItem:
    defaults = {
        "id": MENU_ITEM_ID,
        "tenant_id": TENANT_ID,
        "menu_category_id": MENU_CATEGORY_ID,
        "name": "Burger",
        "price_amount": Decimal("8.99"),
        "currency_code": "USD",
        "is_available": True,
        "display_order": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return MenuItem(**defaults)


def _order(**overrides) -> Order:
    defaults = {
        "id": ORDER_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "order_source": OrderSource.POS,
        "status": OrderStatus.OPEN,
        "subtotal_amount": Decimal(0),
        "tax_amount": Decimal(0),
        "currency_code": "USD",
        "opened_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Order(**defaults)


def _order_item(**overrides) -> OrderItem:
    defaults = {
        "id": "01ARZ3NDEKTSV4RRFFQ6OITM01",
        "tenant_id": TENANT_ID,
        "order_id": ORDER_ID,
        "menu_item_id": MENU_ITEM_ID,
        "quantity": 2,
        "unit_price_amount": Decimal("8.99"),
        "line_status": OrderItemLineStatus.ADDED,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return OrderItem(**defaults)


class TestCreateOrderUseCase:
    def _use_case(self, branch_repo, restaurant_repo, table_repo, tab_repo, order_repo, outbox):
        return CreateOrderUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            restaurant_repository_factory=lambda _s: restaurant_repo,
            table_repository_factory=lambda _s: table_repo,
            tab_repository_factory=lambda _s: tab_repo,
            order_repository_factory=lambda _s: order_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_creates_open_order_with_zero_totals_and_publishes_order_placed(self) -> None:
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()}),
            InMemoryTableRepository(),
            InMemoryTabRepository(),
            InMemoryOrderRepository(),
            outbox,
        )

        result = await use_case.execute(
            TENANT_ID, CreateOrderRequestDTO(branch_id=BRANCH_ID, order_source="pos")
        )

        assert result.status == OrderStatus.OPEN.value
        assert result.subtotal_amount == Decimal(0)
        assert result.currency_code == "USD"
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], OrderPlaced)

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository(),
            InMemoryRestaurantRepository(),
            InMemoryTableRepository(),
            InMemoryTabRepository(),
            InMemoryOrderRepository(),
            FakeOutboxWriter(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID, CreateOrderRequestDTO(branch_id=BRANCH_ID, order_source="pos")
            )


class TestGetOrderUseCase:
    async def test_returns_order_with_its_items(self) -> None:
        use_case = GetOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(
                {ORDER_ID: _order()}, {"item-1": _order_item()}
            ),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, ORDER_ID)

        assert result.id == ORDER_ID
        assert len(result.items) == 1

    async def test_raises_not_found_for_an_order_at_a_different_branch(self) -> None:
        use_case = GetOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(
                {ORDER_ID: _order(branch_id="other-branch")}
            ),
        )

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, ORDER_ID)


class TestListOrdersUseCase:
    async def test_lists_orders_for_the_branch_paginated(self) -> None:
        orders = {f"order-{i}": _order(id=f"order-{i}") for i in range(3)}
        use_case = ListOrdersUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(orders),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=2)

        assert result.total == 3
        assert len(result.orders) == 2


class TestAddOrderItemUseCase:
    def _use_case(self, order_repo, branch_repo, menu_item_repo, menu_category_repo, resolved):
        return AddOrderItemUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: order_repo,
            branch_repository_factory=lambda _s: branch_repo,
            menu_item_repository_factory=lambda _s: menu_item_repo,
            menu_category_repository_factory=lambda _s: menu_category_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_adds_item_and_accumulates_subtotal(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()}),
            InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=2),
        )

        assert result.subtotal_amount == Decimal("17.98")
        assert len(result.items) == 1

    async def test_raises_not_found_for_a_menu_item_in_a_different_restaurant(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()}),
            InMemoryMenuCategoryRepository(
                {
                    MENU_CATEGORY_ID: _menu_category(restaurant_id=OTHER_RESTAURANT_ID),
                }
            ),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )

    async def test_raises_not_available_when_menu_item_is_unavailable(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item(is_available=False)}),
            InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        with pytest.raises(MenuItemNotAvailableError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )

    async def test_raises_invalid_transition_when_order_is_not_open(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order(status=OrderStatus.FIRED)}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()}),
            InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        with pytest.raises(InvalidOrderStatusTransitionError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )

    async def test_no_grant_at_all_is_denied(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()}),
            InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()}),
            ResolvedPermissions(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )


class TestFireOrderUseCase:
    def _use_case(self, order_repo, kitchen_ticket_repo, branch_repo, outbox):
        return FireOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: order_repo,
            kitchen_ticket_repository_factory=lambda _s: kitchen_ticket_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_fires_added_items_and_creates_one_kitchen_ticket(self) -> None:
        outbox = FakeOutboxWriter()
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()}, {"item-1": _order_item()})
        use_case = self._use_case(
            order_repo,
            InMemoryKitchenTicketRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            outbox,
        )

        result = await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        assert result.status == OrderStatus.FIRED.value
        assert result.items[0].line_status == OrderItemLineStatus.FIRED.value
        assert any(isinstance(e[1], OrderFired) for e in outbox.published)

    async def test_raises_has_no_items_for_an_empty_order(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryKitchenTicketRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
        )

        with pytest.raises(OrderHasNoItemsError):
            await use_case.execute(TENANT_ID, "user-1", ORDER_ID)


class TestCloseOrderUseCase:
    async def test_closes_a_fired_order_and_publishes_order_closed(self) -> None:
        outbox = FakeOutboxWriter()
        use_case = CloseOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(
                {ORDER_ID: _order(status=OrderStatus.FIRED)}
            ),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: outbox,
        )

        result = await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        assert result.status == OrderStatus.CLOSED.value
        assert any(isinstance(e[1], OrderClosed) for e in outbox.published)

    async def test_raises_invalid_transition_from_open(self) -> None:
        use_case = CloseOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository({ORDER_ID: _order()}),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(InvalidOrderStatusTransitionError):
            await use_case.execute(TENANT_ID, "user-1", ORDER_ID)


class TestVoidOrderUseCase:
    async def test_voids_an_open_order_and_publishes_order_voided(self) -> None:
        outbox = FakeOutboxWriter()
        use_case = VoidOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository({ORDER_ID: _order()}),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: outbox,
        )

        result = await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        assert result.status == OrderStatus.VOIDED.value
        assert any(isinstance(e[1], OrderVoided) for e in outbox.published)

    async def test_raises_not_found_for_an_unknown_order(self) -> None:
        use_case = VoidOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", ORDER_ID)
