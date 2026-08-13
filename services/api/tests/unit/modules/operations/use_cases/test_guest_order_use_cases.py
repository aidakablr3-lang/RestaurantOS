"""Unit tests for the guest QR ordering use cases (guest ordering) --
in-memory fakes, no network/DB access.

Covers ``GuestAddOrderItemUseCase``, ``GuestSubmitOrderUseCase``, and
``GuestGetOrderUseCase``. All three share ``ensure_guest_order_access``
(``_guest_order_guard.py``): an order whose ``branch_id``/``table_id``
doesn't match the caller's freshly resolved QR token collapses into the
same ``OrderNotFoundError`` as an order that doesn't exist -- covered
once per use case here, not just for one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.operations.application.dto import AddOrderItemRequestDTO
from restaurant_os_api.modules.operations.application.use_cases import (
    GuestAddOrderItemUseCase,
    GuestGetOrderUseCase,
    GuestSubmitOrderUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import (
    Order,
    OrderItem,
    OrderItemLineStatus,
    OrderSource,
    OrderStatus,
)
from restaurant_os_api.modules.operations.domain.events import OrderFired
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
    MenuItemStation,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryKitchenTicketRepository,
    InMemoryOrderRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import (
    InMemoryBranchRepository,
    InMemoryMenuCategoryRepository,
    InMemoryMenuItemRepository,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
OTHER_BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABL01"
OTHER_TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABL02"
MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT01"
MENU_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6MITM01"
ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR01"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


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
        "order_source": OrderSource.QR,
        "status": OrderStatus.OPEN,
        "subtotal_amount": Decimal(0),
        "tax_amount": Decimal(0),
        "currency_code": "USD",
        "opened_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
        "table_id": TABLE_ID,
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


class TestGuestAddOrderItemUseCase:
    def _use_case(self, order_repo, branch_repo=None, menu_item_repo=None, menu_category_repo=None):
        return GuestAddOrderItemUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: order_repo,
            branch_repository_factory=lambda _s: (
                branch_repo
                if branch_repo is not None
                else InMemoryBranchRepository({BRANCH_ID: _branch()})
            ),
            menu_item_repository_factory=lambda _s: (
                menu_item_repo
                if menu_item_repo is not None
                else InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
            ),
            menu_category_repository_factory=lambda _s: (
                menu_category_repo
                if menu_category_repo is not None
                else InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()})
            ),
        )

    async def test_adds_item_and_accumulates_subtotal(self) -> None:
        use_case = self._use_case(InMemoryOrderRepository({ORDER_ID: _order()}))

        result = await use_case.execute(
            TENANT_ID,
            BRANCH_ID,
            TABLE_ID,
            AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=2),
        )

        assert result.subtotal_amount == Decimal("17.98")
        assert len(result.items) == 1

    async def test_adds_an_item_to_an_already_fired_order(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order(status=OrderStatus.FIRED)})
        )

        result = await use_case.execute(
            TENANT_ID,
            BRANCH_ID,
            TABLE_ID,
            AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
        )

        assert result.status == OrderStatus.FIRED.value

    async def test_raises_not_available_when_menu_item_is_unavailable(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order()}),
            menu_item_repo=InMemoryMenuItemRepository(
                {MENU_ITEM_ID: _menu_item(is_available=False)}
            ),
        )

        with pytest.raises(MenuItemNotAvailableError):
            await use_case.execute(
                TENANT_ID,
                BRANCH_ID,
                TABLE_ID,
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )

    async def test_raises_invalid_transition_when_order_is_closed(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order(status=OrderStatus.CLOSED)})
        )

        with pytest.raises(InvalidOrderStatusTransitionError):
            await use_case.execute(
                TENANT_ID,
                BRANCH_ID,
                TABLE_ID,
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )

    async def test_raises_not_found_for_a_missing_order(self) -> None:
        use_case = self._use_case(InMemoryOrderRepository())

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(
                TENANT_ID,
                BRANCH_ID,
                TABLE_ID,
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )

    async def test_raises_not_found_for_an_order_at_a_different_table(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order(table_id=OTHER_TABLE_ID)})
        )

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(
                TENANT_ID,
                BRANCH_ID,
                TABLE_ID,
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )

    async def test_raises_not_found_for_an_order_at_a_different_branch(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order(branch_id=OTHER_BRANCH_ID)})
        )

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(
                TENANT_ID,
                BRANCH_ID,
                TABLE_ID,
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )

    async def test_raises_not_found_for_a_menu_item_in_a_different_restaurant(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order()}),
            menu_category_repo=InMemoryMenuCategoryRepository(
                {MENU_CATEGORY_ID: _menu_category(restaurant_id="a-different-restaurant")}
            ),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                BRANCH_ID,
                TABLE_ID,
                AddOrderItemRequestDTO(order_id=ORDER_ID, menu_item_id=MENU_ITEM_ID, quantity=1),
            )


class TestGuestSubmitOrderUseCase:
    def _use_case(self, order_repo, kitchen_ticket_repo=None, menu_item_repo=None, outbox=None):
        return GuestSubmitOrderUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: order_repo,
            kitchen_ticket_repository_factory=lambda _s: (
                kitchen_ticket_repo
                if kitchen_ticket_repo is not None
                else InMemoryKitchenTicketRepository()
            ),
            menu_item_repository_factory=lambda _s: (
                menu_item_repo
                if menu_item_repo is not None
                else InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
            ),
            outbox_writer_factory=lambda _s: outbox if outbox is not None else FakeOutboxWriter(),
        )

    async def test_fires_added_items_and_creates_a_kitchen_ticket(self) -> None:
        outbox = FakeOutboxWriter()
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()}, {"item-1": _order_item()})
        use_case = self._use_case(order_repo, outbox=outbox)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)

        assert result.status == OrderStatus.FIRED.value
        assert result.items[0].line_status == OrderItemLineStatus.FIRED.value
        assert any(isinstance(e[1], OrderFired) for e in outbox.published)

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
            order_repo, kitchen_ticket_repo=kitchen_ticket_repo, menu_item_repo=menu_item_repo
        )

        await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)

        stations = sorted(t.station for t in kitchen_ticket_repo._tickets.values())
        assert stations == ["bar", "kitchen"]

    async def test_raises_has_no_items_for_an_empty_order(self) -> None:
        use_case = self._use_case(InMemoryOrderRepository({ORDER_ID: _order()}))

        with pytest.raises(OrderHasNoItemsError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)

    async def test_raises_not_found_for_an_order_at_a_different_table(self) -> None:
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order(table_id=OTHER_TABLE_ID)}, {"item-1": _order_item()}
        )
        use_case = self._use_case(order_repo)

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)

    async def test_reentrant_submit_creates_a_second_ticket_for_new_items_only(self) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()}, {"item-1": _order_item()})
        kitchen_ticket_repo = InMemoryKitchenTicketRepository()
        use_case = self._use_case(order_repo, kitchen_ticket_repo=kitchen_ticket_repo)
        await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)
        assert len(kitchen_ticket_repo._tickets) == 1

        order_repo._items["item-2"] = _order_item(
            id="01ARZ3NDEKTSV4RRFFQ6OITM02", line_status=OrderItemLineStatus.ADDED
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)

        assert result.status == OrderStatus.FIRED.value
        assert len(kitchen_ticket_repo._tickets) == 2


class TestGuestGetOrderUseCase:
    def _use_case(self, order_repo) -> GuestGetOrderUseCase:
        return GuestGetOrderUseCase(
            session_factory=_session_factory(), order_repository_factory=lambda _s: order_repo
        )

    async def test_returns_the_order_at_its_own_table(self) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()}, {"item-1": _order_item()})
        use_case = self._use_case(order_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)

        assert result.id == ORDER_ID
        assert len(result.items) == 1

    async def test_raises_not_found_for_a_missing_order(self) -> None:
        use_case = self._use_case(InMemoryOrderRepository())

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)

    async def test_raises_not_found_for_an_order_at_a_different_table(self) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order(table_id=OTHER_TABLE_ID)})
        use_case = self._use_case(order_repo)

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)

    async def test_raises_not_found_for_an_order_at_a_different_branch(self) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order(branch_id=OTHER_BRANCH_ID)})
        use_case = self._use_case(order_repo)

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID, ORDER_ID)
