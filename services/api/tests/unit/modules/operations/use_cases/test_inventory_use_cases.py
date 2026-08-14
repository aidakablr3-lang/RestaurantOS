"""Unit tests for Inventory use cases (Sprint 7 Step 5) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import (
    CreateInventoryCategoryRequestDTO,
    CreateInventoryItemRequestDTO,
    RecordStockMovementRequestDTO,
    UpdateInventoryItemRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    CreateInventoryCategoryUseCase,
    CreateInventoryItemUseCase,
    GetInventoryItemUseCase,
    ListInventoryCategoriesUseCase,
    ListInventoryItemsUseCase,
    ListStockMovementsUseCase,
    RecordStockMovementUseCase,
    UpdateInventoryItemUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import (
    InventoryCategory,
    InventoryCategoryType,
    InventoryItem,
    StockMovement,
    StockMovementType,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    InsufficientStockError,
    InventoryCategoryNameConflictError,
    InventoryCategoryNotFoundError,
    InventoryItemNameConflictError,
    InventoryItemNotFoundError,
    StockAdjustmentRequiresReasonError,
)
from restaurant_os_api.modules.restaurant.domain.entities import Branch, BranchStatus
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    FakeResolveUserPermissionsUseCase,
    InMemoryInventoryCategoryRepository,
    InMemoryInventoryItemRepository,
    InMemoryStockMovementRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import InMemoryBranchRepository

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
OTHER_BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6CAT001"
OTHER_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6CAT002"
ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6ITEM01"


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


def _category(**overrides) -> InventoryCategory:
    defaults = {
        "id": CATEGORY_ID,
        "tenant_id": TENANT_ID,
        "name": "Produce",
        "category_type": InventoryCategoryType.BEVERAGE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return InventoryCategory(**defaults)


def _item(**overrides) -> InventoryItem:
    defaults = {
        "id": ITEM_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "inventory_category_id": CATEGORY_ID,
        "name": "Tomatoes",
        "unit": "kg",
        "quantity_on_hand": Decimal(10),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return InventoryItem(**defaults)


class TestCreateInventoryCategoryUseCase:
    def _use_case(self, category_repo, resolved: ResolvedPermissions | None = None) -> CreateInventoryCategoryUseCase:
        return CreateInventoryCategoryUseCase(
            session_factory=_session_factory(),
            inventory_category_repository_factory=lambda _s: category_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved or ResolvedPermissions()),
        )

    async def test_creates_a_beverage_category_with_no_menu_permission_needed(self) -> None:
        use_case = self._use_case(InMemoryInventoryCategoryRepository())

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateInventoryCategoryRequestDTO(name="Liquor", category_type="beverage"),
        )

        assert result.name == "Liquor"
        assert result.category_type == "beverage"

    async def test_raises_name_conflict_for_a_duplicate_name(self) -> None:
        use_case = self._use_case(InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}))

        with pytest.raises(InventoryCategoryNameConflictError):
            await use_case.execute(
                TENANT_ID, "user-1", CreateInventoryCategoryRequestDTO(name="Produce", category_type="beverage")
            )

    async def test_a_food_category_requires_inventory_food_manage(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryCategoryRepository(),
            resolved=ResolvedPermissions(tenant_wide=frozenset({"inventory_food.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateInventoryCategoryRequestDTO(name="Produce", category_type="food"),
        )

        assert result.category_type == "food"

    async def test_a_food_category_is_denied_without_inventory_food_manage(self) -> None:
        use_case = self._use_case(InMemoryInventoryCategoryRepository())

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateInventoryCategoryRequestDTO(name="Produce", category_type="food"),
            )

    async def test_a_branch_scoped_inventory_food_manage_grant_is_sufficient_for_a_food_category(
        self,
    ) -> None:
        use_case = self._use_case(
            InMemoryInventoryCategoryRepository(),
            resolved=ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"inventory_food.manage"})}),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateInventoryCategoryRequestDTO(name="Produce", category_type="food"),
        )

        assert result.category_type == "food"


class TestListInventoryCategoriesUseCase:
    def _use_case(self, category_repo, resolved: ResolvedPermissions | None = None) -> ListInventoryCategoriesUseCase:
        return ListInventoryCategoriesUseCase(
            session_factory=_session_factory(),
            inventory_category_repository_factory=lambda _s: category_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved or ResolvedPermissions()),
        )

    async def test_lists_categories_for_the_tenant(self) -> None:
        use_case = self._use_case(InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}))

        result = await use_case.execute(TENANT_ID, "user-1")

        assert len(result.categories) == 1

    async def test_excludes_food_categories_for_a_caller_without_inventory_food_read(self) -> None:
        categories = {
            CATEGORY_ID: _category(category_type=InventoryCategoryType.BEVERAGE),
            OTHER_CATEGORY_ID: _category(
                id=OTHER_CATEGORY_ID, name="Produce", category_type=InventoryCategoryType.FOOD
            ),
        }
        use_case = self._use_case(InMemoryInventoryCategoryRepository(categories))

        result = await use_case.execute(TENANT_ID, "user-1")

        assert len(result.categories) == 1
        assert result.categories[0].id == CATEGORY_ID

    async def test_includes_food_categories_for_a_caller_with_inventory_food_read(self) -> None:
        categories = {
            CATEGORY_ID: _category(category_type=InventoryCategoryType.BEVERAGE),
            OTHER_CATEGORY_ID: _category(
                id=OTHER_CATEGORY_ID, name="Produce", category_type=InventoryCategoryType.FOOD
            ),
        }
        use_case = self._use_case(
            InMemoryInventoryCategoryRepository(categories),
            resolved=ResolvedPermissions(tenant_wide=frozenset({"inventory_food.read"})),
        )

        result = await use_case.execute(TENANT_ID, "user-1")

        assert len(result.categories) == 2


class TestCreateInventoryItemUseCase:
    def _use_case(
        self, branch_repo, category_repo, item_repo, resolved: ResolvedPermissions | None = None
    ) -> CreateInventoryItemUseCase:
        return CreateInventoryItemUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: item_repo,
            inventory_category_repository_factory=lambda _s: category_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved or ResolvedPermissions()),
        )

    async def test_creates_an_item_with_zero_quantity_on_hand(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
            InMemoryInventoryItemRepository(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateInventoryItemRequestDTO(
                branch_id=BRANCH_ID,
                inventory_category_id=CATEGORY_ID,
                name="Tomatoes",
                unit="kg",
            ),
        )

        assert result.quantity_on_hand == Decimal(0)
        assert result.branch_id == BRANCH_ID

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository(),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
            InMemoryInventoryItemRepository(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateInventoryItemRequestDTO(
                    branch_id=BRANCH_ID,
                    inventory_category_id=CATEGORY_ID,
                    name="Tomatoes",
                    unit="kg",
                ),
            )

    async def test_raises_not_found_for_an_unknown_category(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryInventoryCategoryRepository(),
            InMemoryInventoryItemRepository(),
        )

        with pytest.raises(InventoryCategoryNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateInventoryItemRequestDTO(
                    branch_id=BRANCH_ID,
                    inventory_category_id=CATEGORY_ID,
                    name="Tomatoes",
                    unit="kg",
                ),
            )

    async def test_raises_name_conflict_within_the_same_branch(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
        )

        with pytest.raises(InventoryItemNameConflictError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateInventoryItemRequestDTO(
                    branch_id=BRANCH_ID,
                    inventory_category_id=CATEGORY_ID,
                    name="Tomatoes",
                    unit="kg",
                ),
            )

    async def test_an_item_under_a_food_category_requires_inventory_food_manage(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryInventoryCategoryRepository(
                {CATEGORY_ID: _category(category_type=InventoryCategoryType.FOOD)}
            ),
            InMemoryInventoryItemRepository(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateInventoryItemRequestDTO(
                    branch_id=BRANCH_ID,
                    inventory_category_id=CATEGORY_ID,
                    name="Tomatoes",
                    unit="kg",
                ),
            )

    async def test_an_item_under_a_beverage_category_needs_no_inventory_food_manage(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryInventoryCategoryRepository(
                {CATEGORY_ID: _category(category_type=InventoryCategoryType.BEVERAGE)}
            ),
            InMemoryInventoryItemRepository(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateInventoryItemRequestDTO(
                branch_id=BRANCH_ID,
                inventory_category_id=CATEGORY_ID,
                name="Vodka",
                unit="bottle",
            ),
        )

        assert result.name == "Vodka"


class TestGetInventoryItemUseCase:
    def _use_case(self, item_repo, category_repo, resolved: ResolvedPermissions | None = None) -> GetInventoryItemUseCase:
        return GetInventoryItemUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: item_repo,
            inventory_category_repository_factory=lambda _s: category_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved or ResolvedPermissions()),
        )

    async def test_returns_the_item(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
        )

        result = await use_case.execute(TENANT_ID, "user-1", BRANCH_ID, ITEM_ID)

        assert result.id == ITEM_ID

    async def test_raises_not_found_for_an_item_at_a_different_branch(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item(branch_id=OTHER_BRANCH_ID)}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
        )

        with pytest.raises(InventoryItemNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", BRANCH_ID, ITEM_ID)

    async def test_a_food_category_item_requires_inventory_food_read(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository(
                {CATEGORY_ID: _category(category_type=InventoryCategoryType.FOOD)}
            ),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(TENANT_ID, "user-1", BRANCH_ID, ITEM_ID)

    async def test_a_food_category_item_is_visible_with_inventory_food_read(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository(
                {CATEGORY_ID: _category(category_type=InventoryCategoryType.FOOD)}
            ),
            resolved=ResolvedPermissions(tenant_wide=frozenset({"inventory_food.read"})),
        )

        result = await use_case.execute(TENANT_ID, "user-1", BRANCH_ID, ITEM_ID)

        assert result.id == ITEM_ID


class TestListInventoryItemsUseCase:
    def _use_case(
        self, item_repo, category_repo, resolved: ResolvedPermissions | None = None
    ) -> ListInventoryItemsUseCase:
        return ListInventoryItemsUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: item_repo,
            inventory_category_repository_factory=lambda _s: category_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved or ResolvedPermissions()),
        )

    async def test_lists_items_for_the_branch_with_pagination(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
        )

        result = await use_case.execute(TENANT_ID, "user-1", BRANCH_ID, offset=0, limit=20)

        assert result.total == 1
        assert result.items[0].id == ITEM_ID

    async def test_excludes_items_under_food_categories_for_a_caller_without_inventory_food_read(
        self,
    ) -> None:
        food_item_id = "01ARZ3NDEKTSV4RRFFQ6FOODIT"
        items = {
            ITEM_ID: _item(),
            food_item_id: _item(
                id=food_item_id, name="Chicken", inventory_category_id=OTHER_CATEGORY_ID
            ),
        }
        categories = {
            CATEGORY_ID: _category(category_type=InventoryCategoryType.BEVERAGE),
            OTHER_CATEGORY_ID: _category(
                id=OTHER_CATEGORY_ID, name="Produce", category_type=InventoryCategoryType.FOOD
            ),
        }
        use_case = self._use_case(
            InMemoryInventoryItemRepository(items), InMemoryInventoryCategoryRepository(categories)
        )

        result = await use_case.execute(TENANT_ID, "user-1", BRANCH_ID, offset=0, limit=20)

        assert result.total == 1
        assert result.items[0].id == ITEM_ID

    async def test_includes_items_under_food_categories_for_a_caller_with_inventory_food_read(self) -> None:
        food_item_id = "01ARZ3NDEKTSV4RRFFQ6FOODIT"
        items = {
            ITEM_ID: _item(),
            food_item_id: _item(
                id=food_item_id, name="Chicken", inventory_category_id=OTHER_CATEGORY_ID
            ),
        }
        categories = {
            CATEGORY_ID: _category(category_type=InventoryCategoryType.BEVERAGE),
            OTHER_CATEGORY_ID: _category(
                id=OTHER_CATEGORY_ID, name="Produce", category_type=InventoryCategoryType.FOOD
            ),
        }
        use_case = self._use_case(
            InMemoryInventoryItemRepository(items),
            InMemoryInventoryCategoryRepository(categories),
            resolved=ResolvedPermissions(tenant_wide=frozenset({"inventory_food.read"})),
        )

        result = await use_case.execute(TENANT_ID, "user-1", BRANCH_ID, offset=0, limit=20)

        assert result.total == 2


class TestUpdateInventoryItemUseCase:
    def _use_case(
        self, item_repo, category_repo, resolved: ResolvedPermissions | None = None
    ) -> UpdateInventoryItemUseCase:
        return UpdateInventoryItemUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: item_repo,
            inventory_category_repository_factory=lambda _s: category_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved or ResolvedPermissions()),
        )

    async def test_updates_editable_fields_without_touching_quantity_on_hand(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            BRANCH_ID,
            UpdateInventoryItemRequestDTO(
                inventory_item_id=ITEM_ID,
                inventory_category_id=CATEGORY_ID,
                name="Ripe Tomatoes",
                reorder_point=Decimal(5),
                allow_negative_stock_override=None,
            ),
        )

        assert result.name == "Ripe Tomatoes"
        assert result.reorder_point == Decimal(5)
        assert result.quantity_on_hand == Decimal(10)

    async def test_raises_not_found_for_an_item_at_a_different_branch(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item(branch_id=OTHER_BRANCH_ID)}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
        )

        with pytest.raises(InventoryItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                BRANCH_ID,
                UpdateInventoryItemRequestDTO(
                    inventory_item_id=ITEM_ID,
                    inventory_category_id=CATEGORY_ID,
                    name="Ripe Tomatoes",
                    reorder_point=None,
                    allow_negative_stock_override=None,
                ),
            )

    async def test_raises_not_found_when_moved_to_an_unknown_category(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository(),
        )

        with pytest.raises(InventoryCategoryNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                BRANCH_ID,
                UpdateInventoryItemRequestDTO(
                    inventory_item_id=ITEM_ID,
                    inventory_category_id=OTHER_CATEGORY_ID,
                    name="Tomatoes",
                    reorder_point=None,
                    allow_negative_stock_override=None,
                ),
            )

    async def test_raises_name_conflict_when_renamed_to_an_existing_name_in_the_branch(
        self,
    ) -> None:
        other_item = _item(id="other-item", name="Onions")
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item(), "other-item": other_item}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
        )

        with pytest.raises(InventoryItemNameConflictError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                BRANCH_ID,
                UpdateInventoryItemRequestDTO(
                    inventory_item_id=ITEM_ID,
                    inventory_category_id=CATEGORY_ID,
                    name="Onions",
                    reorder_point=None,
                    allow_negative_stock_override=None,
                ),
            )

    async def test_updating_an_item_already_under_a_food_category_requires_inventory_food_manage(
        self,
    ) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository(
                {CATEGORY_ID: _category(category_type=InventoryCategoryType.FOOD)}
            ),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                BRANCH_ID,
                UpdateInventoryItemRequestDTO(
                    inventory_item_id=ITEM_ID,
                    inventory_category_id=CATEGORY_ID,
                    name="Ripe Tomatoes",
                    reorder_point=None,
                    allow_negative_stock_override=None,
                ),
            )

    async def test_moving_an_item_into_a_food_category_requires_inventory_food_manage(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository(
                {
                    CATEGORY_ID: _category(),
                    OTHER_CATEGORY_ID: _category(
                        id=OTHER_CATEGORY_ID,
                        name="Produce",
                        category_type=InventoryCategoryType.FOOD,
                    ),
                }
            ),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                BRANCH_ID,
                UpdateInventoryItemRequestDTO(
                    inventory_item_id=ITEM_ID,
                    inventory_category_id=OTHER_CATEGORY_ID,
                    name="Tomatoes",
                    reorder_point=None,
                    allow_negative_stock_override=None,
                ),
            )

    async def test_a_beverage_item_update_needs_no_inventory_food_manage(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            BRANCH_ID,
            UpdateInventoryItemRequestDTO(
                inventory_item_id=ITEM_ID,
                inventory_category_id=CATEGORY_ID,
                name="Ripe Tomatoes",
                reorder_point=None,
                allow_negative_stock_override=None,
            ),
        )

        assert result.name == "Ripe Tomatoes"


class TestRecordStockMovementUseCase:
    def _use_case(
        self, item_repo, movement_repo, branch_repo, resolved, outbox
    ) -> RecordStockMovementUseCase:
        return RecordStockMovementUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: item_repo,
            stock_movement_repository_factory=lambda _s: movement_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved or ResolvedPermissions()),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_adjustment_movement_updates_the_balance_and_creates_an_adjustment_row(
        self,
    ) -> None:
        items = {ITEM_ID: _item(quantity_on_hand=Decimal(10))}
        item_repo = InMemoryInventoryItemRepository(items)
        movement_repo = InMemoryStockMovementRepository(inventory_items=items)
        use_case = self._use_case(
            item_repo,
            movement_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"inventory.manage"})),
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordStockMovementRequestDTO(
                inventory_item_id=ITEM_ID,
                movement_type="adjustment",
                quantity_delta=Decimal(5),
                reason="recount",
                approved_by_user_id="user-1",
            ),
        )

        assert result.quantity_delta == Decimal(5)
        updated_item = await item_repo.get_by_id(TENANT_ID, ITEM_ID)
        assert updated_item is not None
        assert updated_item.quantity_on_hand == Decimal(15)

    async def test_waste_movement_forces_a_negative_delta_regardless_of_input_sign(self) -> None:
        items = {ITEM_ID: _item(quantity_on_hand=Decimal(10))}
        item_repo = InMemoryInventoryItemRepository(items)
        movement_repo = InMemoryStockMovementRepository(inventory_items=items)
        use_case = self._use_case(
            item_repo,
            movement_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"inventory.manage"})),
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordStockMovementRequestDTO(
                inventory_item_id=ITEM_ID, movement_type="waste", quantity_delta=Decimal(3)
            ),
        )

        assert result.quantity_delta == Decimal(-3)

    async def test_raises_requires_reason_for_an_adjustment_without_one(self) -> None:
        items = {ITEM_ID: _item()}
        use_case = self._use_case(
            InMemoryInventoryItemRepository(items),
            InMemoryStockMovementRepository(inventory_items=items),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"inventory.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(StockAdjustmentRequiresReasonError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                RecordStockMovementRequestDTO(
                    inventory_item_id=ITEM_ID, movement_type="adjustment", quantity_delta=Decimal(5)
                ),
            )

    async def test_raises_insufficient_stock_when_the_branch_disallows_negative_stock(
        self,
    ) -> None:
        items = {ITEM_ID: _item(quantity_on_hand=Decimal(2))}
        use_case = self._use_case(
            InMemoryInventoryItemRepository(items),
            InMemoryStockMovementRepository(inventory_items=items),
            InMemoryBranchRepository({BRANCH_ID: _branch(allow_negative_stock=False)}),
            ResolvedPermissions(tenant_wide=frozenset({"inventory.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(InsufficientStockError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                RecordStockMovementRequestDTO(
                    inventory_item_id=ITEM_ID, movement_type="waste", quantity_delta=Decimal(5)
                ),
            )

    async def test_negative_stock_is_allowed_when_the_item_override_permits_it(self) -> None:
        items = {ITEM_ID: _item(quantity_on_hand=Decimal(2), allow_negative_stock_override=True)}
        use_case = self._use_case(
            InMemoryInventoryItemRepository(items),
            InMemoryStockMovementRepository(inventory_items=items),
            InMemoryBranchRepository({BRANCH_ID: _branch(allow_negative_stock=False)}),
            ResolvedPermissions(tenant_wide=frozenset({"inventory.manage"})),
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordStockMovementRequestDTO(
                inventory_item_id=ITEM_ID, movement_type="waste", quantity_delta=Decimal(5)
            ),
        )

        assert result.quantity_delta == Decimal(-5)

    async def test_publishes_low_stock_detected_when_crossing_the_reorder_point(self) -> None:
        items = {ITEM_ID: _item(quantity_on_hand=Decimal(10), reorder_point=Decimal(5))}
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            InMemoryInventoryItemRepository(items),
            InMemoryStockMovementRepository(inventory_items=items),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"inventory.manage"})),
            outbox,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordStockMovementRequestDTO(
                inventory_item_id=ITEM_ID, movement_type="waste", quantity_delta=Decimal(6)
            ),
        )

        assert len(outbox.published) == 1

    async def test_raises_not_found_for_an_unknown_item(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository(),
            InMemoryStockMovementRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"inventory.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(InventoryItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                RecordStockMovementRequestDTO(
                    inventory_item_id=ITEM_ID, movement_type="waste", quantity_delta=Decimal(1)
                ),
            )

    async def test_no_grant_at_all_is_denied(self) -> None:
        items = {ITEM_ID: _item()}
        use_case = self._use_case(
            InMemoryInventoryItemRepository(items),
            InMemoryStockMovementRepository(inventory_items=items),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(),
            FakeOutboxWriter(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                RecordStockMovementRequestDTO(
                    inventory_item_id=ITEM_ID, movement_type="waste", quantity_delta=Decimal(1)
                ),
            )


class TestListStockMovementsUseCase:
    def _use_case(
        self, item_repo, movement_repo, branch_repo, resolved
    ) -> ListStockMovementsUseCase:
        return ListStockMovementsUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: item_repo,
            stock_movement_repository_factory=lambda _s: movement_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved or ResolvedPermissions()),
        )

    async def test_lists_movements_for_an_item(self) -> None:
        items = {ITEM_ID: _item()}
        item_repo = InMemoryInventoryItemRepository(items)
        movement_repo = InMemoryStockMovementRepository(inventory_items=items)
        use_case = self._use_case(
            item_repo,
            movement_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"inventory.read"})),
        )
        await movement_repo.create_movement(
            StockMovement(
                id="movement-1",
                tenant_id=TENANT_ID,
                branch_id=BRANCH_ID,
                inventory_item_id=ITEM_ID,
                movement_type=StockMovementType.ADJUSTMENT,
                quantity_delta=Decimal(1),
                occurred_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
            )
        )

        result = await use_case.execute(TENANT_ID, "user-1", ITEM_ID, offset=0, limit=20)

        assert result.total == 1

    async def test_raises_not_found_for_an_unknown_item(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository(),
            InMemoryStockMovementRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"inventory.read"})),
        )

        with pytest.raises(InventoryItemNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", ITEM_ID, offset=0, limit=20)
