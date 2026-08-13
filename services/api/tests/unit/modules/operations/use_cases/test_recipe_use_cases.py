"""Unit tests for Recipe use cases (Sprint 7 Step 5) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.operations.application.dto import (
    ReviseRecipeIngredientRequestDTO,
    ReviseRecipeRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    GetMenuItemRecipeUseCase,
    ReviseRecipeUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import InventoryItem, Recipe
from restaurant_os_api.modules.operations.domain.exceptions import (
    InventoryItemNotFoundError,
    RecipeNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.entities import MenuItem
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    InMemoryInventoryItemRepository,
    InMemoryRecipeRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import InMemoryMenuItemRepository

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT01"
MENU_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6MITM01"
INVENTORY_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6IITM01"
RECIPE_ID = "01ARZ3NDEKTSV4RRFFQ6RCP001"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _menu_item(**overrides) -> MenuItem:
    defaults = {
        "id": MENU_ITEM_ID,
        "tenant_id": TENANT_ID,
        "menu_category_id": MENU_CATEGORY_ID,
        "name": "Burger",
        "price_amount": Decimal("9.99"),
        "currency_code": "USD",
        "is_available": True,
        "display_order": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return MenuItem(**defaults)


def _inventory_item(**overrides) -> InventoryItem:
    defaults = {
        "id": INVENTORY_ITEM_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "inventory_category_id": "category-1",
        "name": "Beef Patty",
        "unit": "each",
        "quantity_on_hand": Decimal(100),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return InventoryItem(**defaults)


def _recipe(**overrides) -> Recipe:
    defaults = {
        "id": RECIPE_ID,
        "tenant_id": TENANT_ID,
        "name": "Burger recipe",
        "version": 1,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Recipe(**defaults)


class TestReviseRecipeUseCase:
    def _use_case(self, recipe_repo, inventory_item_repo, menu_item_repo) -> ReviseRecipeUseCase:
        return ReviseRecipeUseCase(
            session_factory=_session_factory(),
            recipe_repository_factory=lambda _s: recipe_repo,
            inventory_item_repository_factory=lambda _s: inventory_item_repo,
            menu_item_repository_factory=lambda _s: menu_item_repo,
        )

    async def test_creates_version_one_for_a_menu_item_with_no_existing_recipe(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        use_case = self._use_case(
            InMemoryRecipeRepository(),
            InMemoryInventoryItemRepository({INVENTORY_ITEM_ID: _inventory_item()}),
            menu_item_repo,
        )

        result = await use_case.execute(
            TENANT_ID,
            ReviseRecipeRequestDTO(
                menu_item_id=MENU_ITEM_ID,
                name="Burger recipe",
                ingredients=[
                    ReviseRecipeIngredientRequestDTO(
                        inventory_item_id=INVENTORY_ITEM_ID, quantity=Decimal(1), unit="each"
                    )
                ],
            ),
        )

        assert result.version == 1
        assert len(result.ingredients) == 1
        updated_menu_item = await menu_item_repo.get_by_id(TENANT_ID, MENU_ITEM_ID)
        assert updated_menu_item is not None
        assert updated_menu_item.recipe_id == result.id

    async def test_revising_an_existing_recipe_increments_version_and_supersedes_the_old_one(
        self,
    ) -> None:
        previous = _recipe(version=3)
        recipe_repo = InMemoryRecipeRepository({RECIPE_ID: previous})
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item(recipe_id=RECIPE_ID)})
        use_case = self._use_case(
            recipe_repo,
            InMemoryInventoryItemRepository({INVENTORY_ITEM_ID: _inventory_item()}),
            menu_item_repo,
        )

        result = await use_case.execute(
            TENANT_ID,
            ReviseRecipeRequestDTO(menu_item_id=MENU_ITEM_ID, name="Burger recipe v4"),
        )

        assert result.version == 4
        superseded = await recipe_repo.get_by_id(TENANT_ID, RECIPE_ID)
        assert superseded is not None
        assert superseded.superseded_by_id == result.id

    async def test_raises_not_found_for_an_unknown_menu_item(self) -> None:
        use_case = self._use_case(
            InMemoryRecipeRepository(),
            InMemoryInventoryItemRepository(),
            InMemoryMenuItemRepository(),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID, ReviseRecipeRequestDTO(menu_item_id=MENU_ITEM_ID, name="Burger recipe")
            )

    async def test_raises_not_found_for_an_unknown_ingredient(self) -> None:
        use_case = self._use_case(
            InMemoryRecipeRepository(),
            InMemoryInventoryItemRepository(),
            InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()}),
        )

        with pytest.raises(InventoryItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                ReviseRecipeRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    name="Burger recipe",
                    ingredients=[
                        ReviseRecipeIngredientRequestDTO(
                            inventory_item_id=INVENTORY_ITEM_ID, quantity=Decimal(1), unit="each"
                        )
                    ],
                ),
            )


class TestGetMenuItemRecipeUseCase:
    def _use_case(self, recipe_repo, menu_item_repo) -> GetMenuItemRecipeUseCase:
        return GetMenuItemRecipeUseCase(
            session_factory=_session_factory(),
            recipe_repository_factory=lambda _s: recipe_repo,
            menu_item_repository_factory=lambda _s: menu_item_repo,
        )

    async def test_returns_the_recipe_with_its_ingredients(self) -> None:
        use_case = self._use_case(
            InMemoryRecipeRepository({RECIPE_ID: _recipe()}),
            InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item(recipe_id=RECIPE_ID)}),
        )

        result = await use_case.execute(TENANT_ID, MENU_ITEM_ID)

        assert result.id == RECIPE_ID

    async def test_raises_not_found_for_an_unknown_menu_item(self) -> None:
        use_case = self._use_case(InMemoryRecipeRepository(), InMemoryMenuItemRepository())

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(TENANT_ID, MENU_ITEM_ID)

    async def test_raises_not_found_when_the_menu_item_has_no_recipe(self) -> None:
        use_case = self._use_case(
            InMemoryRecipeRepository(), InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        )

        with pytest.raises(RecipeNotFoundError):
            await use_case.execute(TENANT_ID, MENU_ITEM_ID)

    async def test_raises_not_found_when_the_referenced_recipe_row_is_missing(self) -> None:
        use_case = self._use_case(
            InMemoryRecipeRepository(),
            InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item(recipe_id=RECIPE_ID)}),
        )

        with pytest.raises(RecipeNotFoundError):
            await use_case.execute(TENANT_ID, MENU_ITEM_ID)
