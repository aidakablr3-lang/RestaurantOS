"""ReviseRecipeUseCase.

``PUT /api/v1/menu-items/{id}/recipe`` -- tenant-wide, gated
``require_permission("menu.manage")`` (Architecture doc SS6: recipes
are menu-adjacent, reuse the Restaurant Platform's existing
``menu.manage`` rather than inventing a new permission). Always creates
a brand-new ``Recipe`` row (``version`` incremented from any existing
one) plus a wholly new set of ``RecipeIngredient`` rows, then repoints
``MenuItem.recipe_id`` -- Recipe is versioned, never edited in place
(see ``recipe.py``'s own docstring), so this use case is both "create"
and "revise" depending on whether the menu item already had a recipe.

**Disclosed modeling gap, inherited from the architecture doc itself,
not introduced here:** ``Recipe`` is tenant-wide (one recipe covers a
``MenuItem`` across every branch it's sold at), but each
``RecipeIngredient.inventory_item_id`` points at one specific,
branch-scoped ``InventoryItem`` row (Architecture doc SS3.6 does not
resolve this tension). This use case only validates that each
referenced ``inventory_item_id`` exists within the tenant -- it does
not (and, as designed, cannot) validate "the right branch's row." Real
per-branch stock-deduction accuracy for a recipe shared across
branches is a known limitation, deferred alongside automatic
sale-deduction itself (not built this step -- see
``stock_movement.py``'s own docstring).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import RecipeDTO, ReviseRecipeRequestDTO
from restaurant_os_api.modules.operations.application.use_cases._recipe_mapper import (
    recipe_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import Recipe, RecipeIngredient
from restaurant_os_api.modules.operations.domain.exceptions import (
    InventoryItemNotFoundError,
    RecipeNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryItemRepository,
    RecipeRepository,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import MenuItemRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "menu.manage"


class ReviseRecipeUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        recipe_repository_factory: Callable[[AsyncSession], RecipeRepository],
        inventory_item_repository_factory: Callable[[AsyncSession], InventoryItemRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
    ) -> None:
        self._session_factory = session_factory
        self._recipe_repository_factory = recipe_repository_factory
        self._inventory_item_repository_factory = inventory_item_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory

    async def execute(self, tenant_id: str, request: ReviseRecipeRequestDTO) -> RecipeDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            recipe_repo = self._recipe_repository_factory(uow.session)
            inventory_item_repo = self._inventory_item_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)

            menu_item = await menu_item_repo.get_by_id(tenant_id, request.menu_item_id)
            if menu_item is None:
                raise MenuItemNotFoundError(request.menu_item_id)

            next_version = 1
            if menu_item.recipe_id is not None:
                previous = await recipe_repo.get_by_id(tenant_id, menu_item.recipe_id)
                if previous is None:
                    raise RecipeNotFoundError(menu_item.recipe_id)
                next_version = previous.version + 1

            new_recipe = await recipe_repo.create(
                Recipe(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    name=request.name,
                    version=next_version,
                    created_at=now,
                )
            )

            if menu_item.recipe_id is not None:
                previous = await recipe_repo.get_by_id(tenant_id, menu_item.recipe_id)
                assert previous is not None
                previous.mark_superseded(new_recipe.id)
                await recipe_repo.update(previous)

            ingredients: list[RecipeIngredient] = []
            for line in request.ingredients:
                inventory_item = await inventory_item_repo.get_by_id(
                    tenant_id, line.inventory_item_id
                )
                if inventory_item is None:
                    raise InventoryItemNotFoundError(line.inventory_item_id)
                ingredient = await recipe_repo.add_ingredient(
                    RecipeIngredient(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        recipe_id=new_recipe.id,
                        inventory_item_id=line.inventory_item_id,
                        quantity=line.quantity,
                        unit=line.unit,
                        created_at=now,
                    )
                )
                ingredients.append(ingredient)

            menu_item.recipe_id = new_recipe.id
            await menu_item_repo.update(menu_item)

        return recipe_to_dto(new_recipe, ingredients)
