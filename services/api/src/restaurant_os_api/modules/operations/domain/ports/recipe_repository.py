"""Repository port for Recipe + RecipeIngredient."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import Recipe, RecipeIngredient


class RecipeRepository(Protocol):
    async def get_by_id(self, tenant_id: str, recipe_id: str) -> Recipe | None: ...

    async def create(self, recipe: Recipe) -> Recipe: ...

    async def update(self, recipe: Recipe) -> Recipe: ...

    async def add_ingredient(self, ingredient: RecipeIngredient) -> RecipeIngredient: ...

    async def list_ingredients_for_recipe(
        self, tenant_id: str, recipe_id: str
    ) -> list[RecipeIngredient]: ...
