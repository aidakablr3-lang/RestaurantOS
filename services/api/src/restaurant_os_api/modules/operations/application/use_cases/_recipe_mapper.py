from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import RecipeDTO, RecipeIngredientDTO
from restaurant_os_api.modules.operations.domain.entities import Recipe, RecipeIngredient


def recipe_ingredient_to_dto(ingredient: RecipeIngredient) -> RecipeIngredientDTO:
    return RecipeIngredientDTO(
        id=ingredient.id,
        recipe_id=ingredient.recipe_id,
        inventory_item_id=ingredient.inventory_item_id,
        quantity=ingredient.quantity,
        unit=ingredient.unit,
        created_at=ingredient.created_at,
    )


def recipe_to_dto(recipe: Recipe, ingredients: list[RecipeIngredient]) -> RecipeDTO:
    return RecipeDTO(
        id=recipe.id,
        tenant_id=recipe.tenant_id,
        name=recipe.name,
        version=recipe.version,
        created_at=recipe.created_at,
        superseded_by_id=recipe.superseded_by_id,
        ingredients=[recipe_ingredient_to_dto(i) for i in ingredients],
    )
