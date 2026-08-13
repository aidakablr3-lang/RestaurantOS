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
    async def test_creates_a_category(self) -> None:
        use_case = CreateInventoryCategoryUseCase(
            session_factory=_session_factory(),
            inventory_category_repository_factory=lambda _s: InMemoryInventoryCategoryRepository(),
        )

        result = await use_case.execute(
            TENANT_ID, CreateInventoryCategoryRequestDTO(name="Produce")
        )

        assert result.name == "Produce"

    async def test_raises_name_conflict_for_a_duplicate_name(self) -> None:
        use_case = CreateInventoryCategoryUseCase(
            session_factory=_session_factory(),
            inventory_category_repository_factory=lambda _s: InMemoryInventoryCategoryRepository(
                {CATEGORY_ID: _category()}
            ),
        )

        with pytest.raises(InventoryCategoryNameConflictError):
            await use_case.execute(TENANT_ID, CreateInventoryCategoryRequestDTO(name="Produce"))


class TestListInventoryCategoriesUseCase:
    async def test_lists_categories_for_the_tenant(self) -> None:
        use_case = ListInventoryCategoriesUseCase(
            session_factory=_session_factory(),
            inventory_category_repository_factory=lambda _s: InMemoryInventoryCategoryRepository(
                {CATEGORY_ID: _category()}
            ),
        )

        result = await use_case.execute(TENANT_ID)

        assert len(result.categories) == 1


class TestCreateInventoryItemUseCase:
    def _use_case(self, branch_repo, category_repo, item_repo) -> CreateInventoryItemUseCase:
        return CreateInventoryItemUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: item_repo,
            inventory_category_repository_factory=lambda _s: category_repo,
            branch_repository_factory=lambda _s: branch_repo,
        )

    async def test_creates_an_item_with_zero_quantity_on_hand(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
            InMemoryInventoryItemRepository(),
        )

        result = await use_case.execute(
            TENANT_ID,
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
                CreateInventoryItemRequestDTO(
                    branch_id=BRANCH_ID,
                    inventory_category_id=CATEGORY_ID,
                    name="Tomatoes",
                    unit="kg",
                ),
            )


class TestGetInventoryItemUseCase:
    async def test_returns_the_item(self) -> None:
        use_case = GetInventoryItemUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: InMemoryInventoryItemRepository(
                {ITEM_ID: _item()}
            ),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, ITEM_ID)

        assert result.id == ITEM_ID

    async def test_raises_not_found_for_an_item_at_a_different_branch(self) -> None:
        use_case = GetInventoryItemUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: InMemoryInventoryItemRepository(
                {ITEM_ID: _item(branch_id=OTHER_BRANCH_ID)}
            ),
        )

        with pytest.raises(InventoryItemNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, ITEM_ID)


class TestListInventoryItemsUseCase:
    async def test_lists_items_for_the_branch_with_pagination(self) -> None:
        use_case = ListInventoryItemsUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: InMemoryInventoryItemRepository(
                {ITEM_ID: _item()}
            ),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.total == 1
        assert result.items[0].id == ITEM_ID


class TestUpdateInventoryItemUseCase:
    def _use_case(self, item_repo, category_repo) -> UpdateInventoryItemUseCase:
        return UpdateInventoryItemUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: item_repo,
            inventory_category_repository_factory=lambda _s: category_repo,
        )

    async def test_updates_editable_fields_without_touching_quantity_on_hand(self) -> None:
        use_case = self._use_case(
            InMemoryInventoryItemRepository({ITEM_ID: _item()}),
            InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}),
        )

        result = await use_case.execute(
            TENANT_ID,
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
                BRANCH_ID,
                UpdateInventoryItemRequestDTO(
                    inventory_item_id=ITEM_ID,
                    inventory_category_id=CATEGORY_ID,
                    name="Onions",
                    reorder_point=None,
                    allow_negative_stock_override=None,
                ),
            )


class TestRecordStockMovementUseCase:
    def _use_case(
        self, item_repo, movement_repo, branch_repo, resolved, outbox
    ) -> RecordStockMovementUseCase:
        return RecordStockMovementUseCase(
            session_factory=_session_factory(),
            inventory_item_repository_factory=lambda _s: item_repo,
            stock_movement_repository_factory=lambda _s: movement_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
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
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
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
