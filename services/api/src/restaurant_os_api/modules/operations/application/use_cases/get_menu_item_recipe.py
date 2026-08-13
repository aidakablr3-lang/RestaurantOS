"""GetMenuItemRecipeUseCase. ``GET /api/v1/menu-items/{id}/recipe`` --
tenant-wide, gated ``require_permission("menu.read")``. Reuses
``RecipeNotFoundError`` for both "the menu item has no recipe set" and
"a referenced recipe row is missing" -- both are a 404 from the
caller's point of view, and the exception is given the menu item's own
id in the first case since there is no recipe id to report."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import RecipeDTO
from restaurant_os_api.modules.operations.application.use_cases._recipe_mapper import (
    recipe_to_dto,
)
from restaurant_os_api.modules.operations.domain.exceptions import RecipeNotFoundError
from restaurant_os_api.modules.operations.domain.ports import RecipeRepository
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import MenuItemRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "menu.read"


class GetMenuItemRecipeUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        recipe_repository_factory: Callable[[AsyncSession], RecipeRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
    ) -> None:
        self._session_factory = session_factory
        self._recipe_repository_factory = recipe_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory

    async def execute(self, tenant_id: str, menu_item_id: str) -> RecipeDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            recipe_repo = self._recipe_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)

            menu_item = await menu_item_repo.get_by_id(tenant_id, menu_item_id)
            if menu_item is None:
                raise MenuItemNotFoundError(menu_item_id)

            if menu_item.recipe_id is None:
                raise RecipeNotFoundError(menu_item_id)

            recipe = await recipe_repo.get_by_id(tenant_id, menu_item.recipe_id)
            if recipe is None:
                raise RecipeNotFoundError(menu_item.recipe_id)

            ingredients = await recipe_repo.list_ingredients_for_recipe(tenant_id, recipe.id)

        return recipe_to_dto(recipe, ingredients)
