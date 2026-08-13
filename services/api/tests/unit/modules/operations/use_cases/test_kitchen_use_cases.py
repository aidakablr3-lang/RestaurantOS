"""Unit tests for Kitchen use cases (Sprint 7 Step 3) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import (
    ChangeKitchenItemStatusRequestDTO,
    ChangeKitchenTicketStatusRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    ListKitchenTicketsUseCase,
    UpdateKitchenItemStatusUseCase,
    UpdateKitchenTicketStatusUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import (
    InventoryItem,
    KitchenItem,
    KitchenItemStatus,
    KitchenTicket,
    KitchenTicketStatus,
    Order,
    OrderItem,
    OrderItemLineStatus,
    OrderSource,
    OrderStatus,
    Recipe,
    RecipeIngredient,
)
from restaurant_os_api.modules.operations.domain.events import OrderServed, TicketReady
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidKitchenItemStatusTransitionError,
    KitchenItemNotFoundError,
    KitchenTicketNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    MenuItem,
    MenuItemStation,
)
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    FakeResolveUserPermissionsUseCase,
    InMemoryInventoryItemRepository,
    InMemoryKitchenTicketRepository,
    InMemoryOrderRepository,
    InMemoryRecipeRepository,
    InMemoryStockMovementRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import InMemoryBranchRepository, InMemoryMenuItemRepository

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR01"
TICKET_ID = "01ARZ3NDEKTSV4RRFFQ6TKT001"
ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6KITM01"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": "restaurant-1",
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _order(**overrides) -> Order:
    defaults = {
        "id": ORDER_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "order_source": OrderSource.POS,
        "status": OrderStatus.FIRED,
        "subtotal_amount": Decimal(10),
        "tax_amount": Decimal(0),
        "currency_code": "USD",
        "opened_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Order(**defaults)


def _ticket(**overrides) -> KitchenTicket:
    defaults = {
        "id": TICKET_ID,
        "tenant_id": TENANT_ID,
        "order_id": ORDER_ID,
        "station": "kitchen",
        "status": KitchenTicketStatus.FIRED,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return KitchenTicket(**defaults)


def _item(**overrides) -> KitchenItem:
    defaults = {
        "id": ITEM_ID,
        "tenant_id": TENANT_ID,
        "kitchen_ticket_id": TICKET_ID,
        "order_item_id": "order-item-1",
        "status": KitchenItemStatus.QUEUED,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return KitchenItem(**defaults)


def _order_item(**overrides) -> OrderItem:
    defaults = {
        "id": "order-item-1",
        "tenant_id": TENANT_ID,
        "order_id": ORDER_ID,
        "menu_item_id": "menu-item-1",
        "quantity": 1,
        "unit_price_amount": Decimal("8.99"),
        "line_status": OrderItemLineStatus.FIRED,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return OrderItem(**defaults)


def _menu_item(**overrides) -> MenuItem:
    defaults = {
        "id": "menu-item-1",
        "tenant_id": TENANT_ID,
        "menu_category_id": "menu-category-1",
        "name": "Burger",
        "price_amount": Decimal("8.99"),
        "currency_code": "USD",
        "is_available": True,
        "display_order": 0,
        "created_at": datetime.now(UTC),
        "recipe_id": None,
        "station": MenuItemStation.KITCHEN,
    }
    defaults.update(overrides)
    return MenuItem(**defaults)


def _recipe(**overrides) -> Recipe:
    defaults = {
        "id": "recipe-1",
        "tenant_id": TENANT_ID,
        "name": "Burger recipe",
        "version": 1,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Recipe(**defaults)


def _recipe_ingredient(**overrides) -> RecipeIngredient:
    defaults = {
        "id": "ingredient-1",
        "tenant_id": TENANT_ID,
        "recipe_id": "recipe-1",
        "inventory_item_id": "inv-item-1",
        "quantity": Decimal(1),
        "unit": "each",
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return RecipeIngredient(**defaults)


def _inventory_item(**overrides) -> InventoryItem:
    defaults = {
        "id": "inv-item-1",
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "inventory_category_id": "inv-category-1",
        "name": "Beef Patty",
        "unit": "each",
        "quantity_on_hand": Decimal(100),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return InventoryItem(**defaults)


class TestListKitchenTicketsUseCase:
    async def test_lists_tickets_for_the_branch_via_the_order_join(self) -> None:
        use_case = ListKitchenTicketsUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket()}, {}, {ORDER_ID: _order()}
            ),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.total == 1
        assert result.tickets[0].id == TICKET_ID

    async def test_excludes_tickets_whose_order_belongs_to_a_different_branch(self) -> None:
        use_case = ListKitchenTicketsUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket()}, {}, {ORDER_ID: _order(branch_id="other-branch")}
            ),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.total == 0


class TestUpdateKitchenTicketStatusUseCase:
    def _use_case(
        self,
        ticket_repo,
        order_repo,
        branch_repo,
        outbox,
        *,
        menu_item_repo=None,
        recipe_repo=None,
        inventory_item_repo=None,
        stock_movement_repo=None,
    ) -> UpdateKitchenTicketStatusUseCase:
        return UpdateKitchenTicketStatusUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: ticket_repo,
            order_repository_factory=lambda _s: order_repo,
            branch_repository_factory=lambda _s: branch_repo,
            menu_item_repository_factory=lambda _s: menu_item_repo or InMemoryMenuItemRepository(),
            recipe_repository_factory=lambda _s: recipe_repo or InMemoryRecipeRepository(),
            inventory_item_repository_factory=lambda _s: (
                inventory_item_repo or InMemoryInventoryItemRepository()
            ),
            stock_movement_repository_factory=lambda _s: (
                stock_movement_repo or InMemoryStockMovementRepository()
            ),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"kitchen.manage"}))
            ),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_marks_ready_and_publishes_ticket_ready(self) -> None:
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket(status=KitchenTicketStatus.IN_PROGRESS)}
            ),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="ready"),
        )

        assert result.status == KitchenTicketStatus.READY.value
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], TicketReady)

    async def test_start_does_not_publish_ticket_ready(self) -> None:
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            InMemoryKitchenTicketRepository({TICKET_ID: _ticket()}),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="in_progress"),
        )

        assert result.status == KitchenTicketStatus.IN_PROGRESS.value
        assert len(outbox.published) == 0

    async def test_starting_a_ticket_cascades_queued_items_to_in_progress(self) -> None:
        ticket_repo = InMemoryKitchenTicketRepository(
            {TICKET_ID: _ticket()},
            {
                ITEM_ID: _item(),
                "item-2": _item(id="item-2", status=KitchenItemStatus.IN_PROGRESS),
            },
        )
        use_case = self._use_case(
            ticket_repo,
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="in_progress"),
        )

        statuses = {item.id: item.status for item in result.items}
        assert statuses[ITEM_ID] == KitchenItemStatus.IN_PROGRESS.value
        assert statuses["item-2"] == KitchenItemStatus.IN_PROGRESS.value

    async def test_marking_ready_cascades_a_still_queued_item_through_in_progress(self) -> None:
        ticket_repo = InMemoryKitchenTicketRepository(
            {TICKET_ID: _ticket(status=KitchenTicketStatus.IN_PROGRESS)},
            {
                ITEM_ID: _item(),
                "item-2": _item(id="item-2", status=KitchenItemStatus.READY),
            },
        )
        use_case = self._use_case(
            ticket_repo,
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="ready"),
        )

        statuses = {item.id: item.status for item in result.items}
        assert statuses[ITEM_ID] == KitchenItemStatus.READY.value
        assert statuses["item-2"] == KitchenItemStatus.READY.value

    async def test_serving_a_ticket_does_not_touch_item_statuses(self) -> None:
        ticket_repo = InMemoryKitchenTicketRepository(
            {TICKET_ID: _ticket(status=KitchenTicketStatus.READY)},
            {ITEM_ID: _item(status=KitchenItemStatus.READY)},
        )
        use_case = self._use_case(
            ticket_repo,
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="served"),
        )

        assert result.status == KitchenTicketStatus.SERVED.value
        assert result.items[0].status == KitchenItemStatus.READY.value

    async def test_marking_ready_cascades_the_linked_order_item_to_ready(self) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()}, {"order-item-1": _order_item()})
        ticket_repo = InMemoryKitchenTicketRepository(
            {TICKET_ID: _ticket(status=KitchenTicketStatus.IN_PROGRESS)},
            {ITEM_ID: _item(status=KitchenItemStatus.IN_PROGRESS)},
        )
        use_case = self._use_case(
            ticket_repo,
            order_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="ready"),
        )

        order_item = await order_repo.get_item_by_id(TENANT_ID, "order-item-1")
        assert order_item is not None
        assert order_item.line_status == OrderItemLineStatus.READY

    async def test_marking_served_completes_the_order_once_every_item_is_served(self) -> None:
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order(status=OrderStatus.FIRED)},
            {"order-item-1": _order_item(line_status=OrderItemLineStatus.READY)},
        )
        ticket_repo = InMemoryKitchenTicketRepository(
            {TICKET_ID: _ticket(status=KitchenTicketStatus.READY)},
            {ITEM_ID: _item(status=KitchenItemStatus.READY)},
        )
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            ticket_repo,
            order_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            outbox,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="served"),
        )

        order_item = await order_repo.get_item_by_id(TENANT_ID, "order-item-1")
        assert order_item is not None
        assert order_item.line_status == OrderItemLineStatus.SERVED
        order = await order_repo.get_by_id(TENANT_ID, ORDER_ID)
        assert order is not None
        assert order.status == OrderStatus.SERVED
        assert any(isinstance(e[1], OrderServed) for e in outbox.published)

    async def test_marking_served_deducts_the_recipe_ingredients_from_inventory(self) -> None:
        menu_item_id = "menu-item-1"
        recipe_id = "recipe-1"
        inventory_item_id = "inv-item-1"
        menu_item_repo = InMemoryMenuItemRepository(
            {menu_item_id: _menu_item(id=menu_item_id, recipe_id=recipe_id)}
        )
        recipe_repo = InMemoryRecipeRepository(
            {recipe_id: _recipe(id=recipe_id)},
            {
                "ingredient-1": _recipe_ingredient(
                    recipe_id=recipe_id, inventory_item_id=inventory_item_id, quantity=Decimal(2)
                )
            },
        )
        inventory_items = {
            inventory_item_id: _inventory_item(id=inventory_item_id, quantity_on_hand=Decimal(50))
        }
        inventory_item_repo = InMemoryInventoryItemRepository(inventory_items)
        stock_movement_repo = InMemoryStockMovementRepository(inventory_items=inventory_items)
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order(status=OrderStatus.FIRED)},
            {
                "order-item-1": _order_item(
                    menu_item_id=menu_item_id,
                    quantity=3,
                    line_status=OrderItemLineStatus.READY,
                )
            },
        )
        ticket_repo = InMemoryKitchenTicketRepository(
            {TICKET_ID: _ticket(status=KitchenTicketStatus.READY)},
            {ITEM_ID: _item(status=KitchenItemStatus.READY)},
        )
        use_case = self._use_case(
            ticket_repo,
            order_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
            menu_item_repo=menu_item_repo,
            recipe_repo=recipe_repo,
            inventory_item_repo=inventory_item_repo,
            stock_movement_repo=stock_movement_repo,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="served"),
        )

        inventory_item = await inventory_item_repo.get_by_id(TENANT_ID, inventory_item_id)
        assert inventory_item is not None
        # 2 units/serving * 3 servings = 6 deducted from 50.
        assert inventory_item.quantity_on_hand == Decimal(44)

    async def test_marking_served_leaves_the_order_fired_while_another_item_is_still_pending(
        self,
    ) -> None:
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order(status=OrderStatus.FIRED)},
            {
                "order-item-1": _order_item(line_status=OrderItemLineStatus.READY),
                "order-item-2": _order_item(
                    id="order-item-2", line_status=OrderItemLineStatus.FIRED
                ),
            },
        )
        ticket_repo = InMemoryKitchenTicketRepository(
            {TICKET_ID: _ticket(status=KitchenTicketStatus.READY)},
            {ITEM_ID: _item(status=KitchenItemStatus.READY)},
        )
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            ticket_repo,
            order_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            outbox,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="served"),
        )

        order = await order_repo.get_by_id(TENANT_ID, ORDER_ID)
        assert order is not None
        assert order.status == OrderStatus.FIRED
        assert not any(isinstance(e[1], OrderServed) for e in outbox.published)

    async def test_raises_not_found_for_an_unknown_ticket(self) -> None:
        use_case = self._use_case(
            InMemoryKitchenTicketRepository(),
            InMemoryOrderRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
        )

        with pytest.raises(KitchenTicketNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="ready"),
            )

    async def test_no_grant_at_all_is_denied(self) -> None:
        use_case = UpdateKitchenTicketStatusUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket()}
            ),
            order_repository_factory=lambda _s: InMemoryOrderRepository({ORDER_ID: _order()}),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            menu_item_repository_factory=lambda _s: InMemoryMenuItemRepository(),
            recipe_repository_factory=lambda _s: InMemoryRecipeRepository(),
            inventory_item_repository_factory=lambda _s: InMemoryInventoryItemRepository(),
            stock_movement_repository_factory=lambda _s: InMemoryStockMovementRepository(),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions()
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="ready"),
            )


class TestUpdateKitchenItemStatusUseCase:
    def _use_case(self, ticket_repo, order_repo, branch_repo) -> UpdateKitchenItemStatusUseCase:
        return UpdateKitchenItemStatusUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: ticket_repo,
            order_repository_factory=lambda _s: order_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"kitchen.manage"}))
            ),
        )

    async def test_marks_an_item_ready_independently_of_its_ticket(self) -> None:
        use_case = self._use_case(
            InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket()}, {ITEM_ID: _item(status=KitchenItemStatus.IN_PROGRESS)}
            ),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenItemStatusRequestDTO(kitchen_item_id=ITEM_ID, status="ready"),
        )

        assert result.status == KitchenItemStatus.READY.value

    async def test_raises_invalid_transition_for_an_out_of_order_status(self) -> None:
        use_case = self._use_case(
            InMemoryKitchenTicketRepository({TICKET_ID: _ticket()}, {ITEM_ID: _item()}),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
        )

        with pytest.raises(InvalidKitchenItemStatusTransitionError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeKitchenItemStatusRequestDTO(kitchen_item_id=ITEM_ID, status="ready"),
            )

    async def test_raises_not_found_for_an_unknown_item(self) -> None:
        use_case = self._use_case(
            InMemoryKitchenTicketRepository(),
            InMemoryOrderRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
        )

        with pytest.raises(KitchenItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeKitchenItemStatusRequestDTO(kitchen_item_id=ITEM_ID, status="ready"),
            )
