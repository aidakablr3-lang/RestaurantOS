"""Unit tests for GuestGetMenuUseCase (guest ordering)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.restaurant.application.use_cases import GuestGetMenuUseCase
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    MenuCategory,
    MenuItem,
    Restaurant,
    RestaurantStatus,
    Table,
    TableStatus,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    RestaurantNotFoundError,
    TableNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    InMemoryBranchRepository,
    InMemoryMenuCategoryRepository,
    InMemoryMenuItemRepository,
    InMemoryRestaurantRepository,
    InMemoryTableRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RSTR01"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABLE1"
CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6CTGRY1"
OTHER_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6CTGRY2"
ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6ITEM01"
UNAVAILABLE_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6ITEM02"


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
        "name": "Main Branch",
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


def _category(**overrides) -> MenuCategory:
    defaults = {
        "id": CATEGORY_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Mains",
        "display_order": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return MenuCategory(**defaults)


def _item(**overrides) -> MenuItem:
    defaults = {
        "id": ITEM_ID,
        "tenant_id": TENANT_ID,
        "menu_category_id": CATEGORY_ID,
        "name": "Burger",
        "price_amount": Decimal("12.50"),
        "currency_code": "USD",
        "is_available": True,
        "display_order": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return MenuItem(**defaults)


def _use_case(
    branch_repo,
    category_repo,
    item_repo,
    *,
    restaurant_repo=None,
    table_repo=None,
) -> GuestGetMenuUseCase:
    return GuestGetMenuUseCase(
        session_factory=fake_session_factory_returning(FakeAsyncSession()),
        branch_repository_factory=lambda _s: branch_repo,
        restaurant_repository_factory=lambda _s: (
            restaurant_repo
            if restaurant_repo is not None
            else InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()})
        ),
        table_repository_factory=lambda _s: (
            table_repo if table_repo is not None else InMemoryTableRepository({TABLE_ID: _table()})
        ),
        menu_category_repository_factory=lambda _s: category_repo,
        menu_item_repository_factory=lambda _s: item_repo,
    )


class TestGuestGetMenuUseCase:
    async def test_returns_available_items_grouped_by_category_in_display_order(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        category_repo = InMemoryMenuCategoryRepository({CATEGORY_ID: _category()})
        item_repo = InMemoryMenuItemRepository({ITEM_ID: _item()})
        use_case = _use_case(branch_repo, category_repo, item_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)

        assert result.branch_id == BRANCH_ID
        assert result.table_id == TABLE_ID
        assert result.restaurant_name == "Test Restaurant"
        assert result.branch_name == "Main Branch"
        assert result.table_number == "12"
        assert len(result.categories) == 1
        assert result.categories[0].id == CATEGORY_ID
        assert len(result.categories[0].items) == 1
        assert result.categories[0].items[0].id == ITEM_ID
        assert result.categories[0].items[0].price_amount == Decimal("12.50")

    async def test_unavailable_items_are_filtered_out_entirely(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        category_repo = InMemoryMenuCategoryRepository({CATEGORY_ID: _category()})
        item_repo = InMemoryMenuItemRepository(
            {
                ITEM_ID: _item(),
                UNAVAILABLE_ITEM_ID: _item(id=UNAVAILABLE_ITEM_ID, is_available=False),
            }
        )
        use_case = _use_case(branch_repo, category_repo, item_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)

        item_ids = [item.id for item in result.categories[0].items]
        assert item_ids == [ITEM_ID]

    async def test_a_category_with_only_unavailable_items_is_omitted(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        category_repo = InMemoryMenuCategoryRepository({CATEGORY_ID: _category()})
        item_repo = InMemoryMenuItemRepository({ITEM_ID: _item(is_available=False)})
        use_case = _use_case(branch_repo, category_repo, item_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)

        assert result.categories == []

    async def test_categories_are_sorted_by_display_order(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        category_repo = InMemoryMenuCategoryRepository(
            {
                OTHER_CATEGORY_ID: _category(
                    id=OTHER_CATEGORY_ID, name="Desserts", display_order=1
                ),
                CATEGORY_ID: _category(display_order=0),
            }
        )
        item_repo = InMemoryMenuItemRepository(
            {
                ITEM_ID: _item(),
                UNAVAILABLE_ITEM_ID: _item(
                    id=UNAVAILABLE_ITEM_ID, menu_category_id=OTHER_CATEGORY_ID
                ),
            }
        )
        use_case = _use_case(branch_repo, category_repo, item_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)

        assert [c.id for c in result.categories] == [CATEGORY_ID, OTHER_CATEGORY_ID]

    async def test_a_nonexistent_branch_raises(self) -> None:
        use_case = _use_case(
            InMemoryBranchRepository(), InMemoryMenuCategoryRepository(), InMemoryMenuItemRepository()
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)

    async def test_a_nonexistent_restaurant_raises(self) -> None:
        use_case = _use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryMenuCategoryRepository(),
            InMemoryMenuItemRepository(),
            restaurant_repo=InMemoryRestaurantRepository(),
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)

    async def test_a_nonexistent_table_raises(self) -> None:
        use_case = _use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryMenuCategoryRepository(),
            InMemoryMenuItemRepository(),
            table_repo=InMemoryTableRepository(),
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)
