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
    VoidOrderItemUseCase,
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
    InvalidOrderItemStatusTransitionError,
    InvalidOrderStatusTransitionError,
    MenuItemNotAvailableError,
    OrderHasNoItemsError,
    OrderItemNotFoundError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    MenuCategory,
    MenuItem,
    MenuItemStation,
    Restaurant,
    RestaurantStatus,
    Table,
    TableStatus,
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
ORDER2_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR02"
TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABL01"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ6TNT002"


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


def _table(**overrides) -> Table:
    defaults = {
        "id": TABLE_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "table_zone_id": "table-zone-1",
        "table_number": "12",
        "capacity": 4,
        "status": TableStatus.AVAILABLE,
        "sync_version": 1,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Table(**defaults)


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

    async def test_occupies_the_table_when_a_table_id_is_given(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()}),
            table_repo,
            InMemoryTabRepository(),
            InMemoryOrderRepository(),
            FakeOutboxWriter(),
        )

        await use_case.execute(
            TENANT_ID,
            CreateOrderRequestDTO(branch_id=BRANCH_ID, order_source="pos", table_id=TABLE_ID),
        )

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.OCCUPIED

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

    async def test_filters_by_table_id(self) -> None:
        orders = {
            "order-a": _order(id="order-a", table_id="table-1"),
            "order-b": _order(id="order-b", table_id="table-2"),
        }
        use_case = ListOrdersUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(orders),
        )

        result = await use_case.execute(
            TENANT_ID, BRANCH_ID, offset=0, limit=20, table_id="table-1"
        )

        assert result.total == 1
        assert result.orders[0].id == "order-a"

    async def test_filters_by_status(self) -> None:
        orders = {
            "order-a": _order(id="order-a", status=OrderStatus.OPEN),
            "order-b": _order(id="order-b", status=OrderStatus.FIRED),
        }
        use_case = ListOrdersUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(orders),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20, status="fired")

        assert result.total == 1
        assert result.orders[0].id == "order-b"

    async def test_reports_a_real_item_count_without_populating_items(self) -> None:
        orders = {ORDER_ID: _order()}
        items = {
            "item-1": _order_item(id="item-1"),
            "item-2": _order_item(id="item-2"),
        }
        use_case = ListOrdersUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(orders, items),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.orders[0].item_count == 2
        assert result.orders[0].items == []


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

    async def test_adds_an_item_to_an_already_fired_order(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order(status=OrderStatus.FIRED)}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()}),
            InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
        )

        assert result.status == OrderStatus.FIRED.value
        assert result.items[0].line_status == OrderItemLineStatus.ADDED.value

    async def test_raises_invalid_transition_when_order_is_closed(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order(status=OrderStatus.CLOSED)}),
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
    def _use_case(self, order_repo, kitchen_ticket_repo, branch_repo, outbox, menu_item_repo=None):
        return FireOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: order_repo,
            kitchen_ticket_repository_factory=lambda _s: kitchen_ticket_repo,
            branch_repository_factory=lambda _s: branch_repo,
            menu_item_repository_factory=lambda _s: (
                menu_item_repo
                if menu_item_repo is not None
                else InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
            ),
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

    async def test_refiring_an_already_fired_order_creates_a_second_ticket_for_new_items_only(
        self,
    ) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()}, {"item-1": _order_item()})
        kitchen_ticket_repo = InMemoryKitchenTicketRepository()
        use_case = self._use_case(
            order_repo,
            kitchen_ticket_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
        )
        await use_case.execute(TENANT_ID, "user-1", ORDER_ID)
        assert len(kitchen_ticket_repo._tickets) == 1

        order_repo._items["item-2"] = _order_item(
            id="01ARZ3NDEKTSV4RRFFQ6OITM02", line_status=OrderItemLineStatus.ADDED
        )

        result = await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        assert result.status == OrderStatus.FIRED.value
        assert len(kitchen_ticket_repo._tickets) == 2
        assert all(item.line_status == OrderItemLineStatus.FIRED.value for item in result.items)

    async def test_routes_fired_items_into_one_ticket_per_distinct_station(self) -> None:
        other_menu_item_id = "01ARZ3NDEKTSV4RRFFQ6MITM02"
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order()},
            {
                "item-1": _order_item(),
                "item-2": _order_item(
                    id="01ARZ3NDEKTSV4RRFFQ6OITM02", menu_item_id=other_menu_item_id
                ),
            },
        )
        menu_item_repo = InMemoryMenuItemRepository(
            {
                MENU_ITEM_ID: _menu_item(station=MenuItemStation.KITCHEN),
                other_menu_item_id: _menu_item(id=other_menu_item_id, station=MenuItemStation.BAR),
            }
        )
        kitchen_ticket_repo = InMemoryKitchenTicketRepository()
        use_case = self._use_case(
            order_repo,
            kitchen_ticket_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
            menu_item_repo=menu_item_repo,
        )

        await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        stations = sorted(t.station for t in kitchen_ticket_repo._tickets.values())
        assert stations == ["bar", "kitchen"]

    async def test_refiring_with_nothing_new_raises_has_no_items(self) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()}, {"item-1": _order_item()})
        use_case = self._use_case(
            order_repo,
            InMemoryKitchenTicketRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
        )
        await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

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
            table_repository_factory=lambda _s: InMemoryTableRepository(),
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
            table_repository_factory=lambda _s: InMemoryTableRepository(),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(InvalidOrderStatusTransitionError):
            await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

    async def test_closing_a_table_order_marks_the_table_available(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = CloseOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(
                {ORDER_ID: _order(status=OrderStatus.FIRED, table_id=TABLE_ID)}
            ),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            table_repository_factory=lambda _s: table_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.AVAILABLE

    async def test_closing_one_order_leaves_the_table_occupied_when_a_sibling_is_still_active(
        self,
    ) -> None:
        # Defect #1 remediation: closing this order must not release the
        # table while a second, still-active order sits on it.
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = CloseOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(
                {
                    ORDER_ID: _order(status=OrderStatus.FIRED, table_id=TABLE_ID),
                    ORDER2_ID: _order(id=ORDER2_ID, status=OrderStatus.FIRED, table_id=TABLE_ID),
                }
            ),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            table_repository_factory=lambda _s: table_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.OCCUPIED

    async def test_closing_does_not_override_a_manually_cleaning_table(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.CLEANING)})
        use_case = CloseOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(
                {ORDER_ID: _order(status=OrderStatus.FIRED, table_id=TABLE_ID)}
            ),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            table_repository_factory=lambda _s: table_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.CLEANING


class TestVoidOrderUseCase:
    async def test_voids_an_open_order_and_publishes_order_voided(self) -> None:
        outbox = FakeOutboxWriter()
        use_case = VoidOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository({ORDER_ID: _order()}),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            table_repository_factory=lambda _s: InMemoryTableRepository(),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: outbox,
        )

        result = await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        assert result.status == OrderStatus.VOIDED.value
        assert any(isinstance(e[1], OrderVoided) for e in outbox.published)

    async def test_voiding_a_table_order_marks_the_table_available(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = VoidOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(
                {ORDER_ID: _order(table_id=TABLE_ID)}
            ),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            table_repository_factory=lambda _s: table_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.AVAILABLE

    async def test_voiding_one_order_leaves_the_table_occupied_when_a_sibling_is_still_active(
        self,
    ) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = VoidOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(
                {
                    ORDER_ID: _order(table_id=TABLE_ID),
                    ORDER2_ID: _order(id=ORDER2_ID, status=OrderStatus.FIRED, table_id=TABLE_ID),
                }
            ),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            table_repository_factory=lambda _s: table_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        await use_case.execute(TENANT_ID, "user-1", ORDER_ID)

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.OCCUPIED

    async def test_raises_not_found_for_an_unknown_order(self) -> None:
        use_case = VoidOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: InMemoryOrderRepository(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            table_repository_factory=lambda _s: InMemoryTableRepository(),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"order.manage"}))
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", ORDER_ID)


class TestVoidOrderItemUseCase:
    def _use_case(self, order_repo, branch_repo, resolved):
        return VoidOrderItemUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: order_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_voids_an_added_item_and_backs_out_its_cost(self) -> None:
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order(subtotal_amount=Decimal("17.98"))},
            {"item-1": _order_item()},
        )
        use_case = self._use_case(
            order_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        result = await use_case.execute(TENANT_ID, "user-1", ORDER_ID, "item-1")

        assert result.items[0].line_status == OrderItemLineStatus.VOIDED.value
        assert result.subtotal_amount == Decimal(0)

    async def test_raises_not_found_for_an_unknown_order(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", ORDER_ID, "item-1")

    async def test_raises_not_found_for_an_item_belonging_to_a_different_order(self) -> None:
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order(), "other-order": _order(id="other-order")},
            {"item-1": _order_item(order_id="other-order")},
        )
        use_case = self._use_case(
            order_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        with pytest.raises(OrderItemNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", ORDER_ID, "item-1")

    async def test_raises_invalid_transition_when_item_is_already_fired(self) -> None:
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order(status=OrderStatus.FIRED)},
            {"item-1": _order_item(line_status=OrderItemLineStatus.FIRED)},
        )
        use_case = self._use_case(
            order_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        with pytest.raises(InvalidOrderItemStatusTransitionError):
            await use_case.execute(TENANT_ID, "user-1", ORDER_ID, "item-1")

    async def test_no_grant_at_all_is_denied(self) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()}, {"item-1": _order_item()})
        use_case = self._use_case(
            order_repo, InMemoryBranchRepository({BRANCH_ID: _branch()}), ResolvedPermissions()
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(TENANT_ID, "user-1", ORDER_ID, "item-1")


class TestHasActiveOrdersForTable:
    """Direct repository-level coverage for the query the Defect #1
    remediation added -- ``release_table_if_occupied`` relies on this
    being scoped correctly per tenant and per table."""

    async def test_true_when_an_open_order_exists_for_the_table(self) -> None:
        repo = InMemoryOrderRepository({ORDER_ID: _order(table_id=TABLE_ID)})

        assert await repo.has_active_orders_for_table(TENANT_ID, TABLE_ID) is True

    async def test_false_when_the_only_order_is_closed(self) -> None:
        repo = InMemoryOrderRepository(
            {ORDER_ID: _order(table_id=TABLE_ID, status=OrderStatus.CLOSED)}
        )

        assert await repo.has_active_orders_for_table(TENANT_ID, TABLE_ID) is False

    async def test_false_when_the_only_order_is_voided(self) -> None:
        repo = InMemoryOrderRepository(
            {ORDER_ID: _order(table_id=TABLE_ID, status=OrderStatus.VOIDED)}
        )

        assert await repo.has_active_orders_for_table(TENANT_ID, TABLE_ID) is False

    async def test_false_for_an_active_order_belonging_to_another_tenant(self) -> None:
        repo = InMemoryOrderRepository(
            {ORDER_ID: _order(tenant_id=OTHER_TENANT_ID, table_id=TABLE_ID)}
        )

        assert await repo.has_active_orders_for_table(TENANT_ID, TABLE_ID) is False

    async def test_false_for_an_active_order_on_a_different_table(self) -> None:
        other_table_id = "01ARZ3NDEKTSV4RRFFQ6TABL02"
        repo = InMemoryOrderRepository({ORDER_ID: _order(table_id=other_table_id)})

        assert await repo.has_active_orders_for_table(TENANT_ID, TABLE_ID) is False
