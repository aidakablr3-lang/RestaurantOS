"""Recipe endpoint (Sprint 7 Step 5). ``/api/v1/menu-items/{id}/recipe``
-- flat, tenant-wide, reuses the Restaurant Platform's existing
``menu.manage``/``menu.read`` permissions directly (Architecture doc
SS6: recipes are menu-adjacent, not a new permission)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, status

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.operations.application.dto import (
    RecipeDTO,
    ReviseRecipeIngredientRequestDTO,
    ReviseRecipeRequestDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    GetMenuItemRecipeUseCaseDep,
    ReviseRecipeUseCaseDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.recipe_schemas import (
    RecipeIngredientResponseSchema,
    RecipeResponseSchema,
    ReviseRecipeRequestSchema,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    RequireMenuManageDep,
    RequireMenuReadDep,
)

router = APIRouter(tags=["recipes"])

MenuItemIdPath = Annotated[str, Path(min_length=26, max_length=26)]


def _recipe_to_schema(dto: RecipeDTO) -> RecipeResponseSchema:
    return RecipeResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        name=dto.name,
        version=dto.version,
        created_at=dto.created_at,
        superseded_by_id=dto.superseded_by_id,
        ingredients=[
            RecipeIngredientResponseSchema(
                id=i.id,
                recipe_id=i.recipe_id,
                inventory_item_id=i.inventory_item_id,
                quantity=i.quantity,
                unit=i.unit,
                created_at=i.created_at,
            )
            for i in dto.ingredients
        ],
    )


@router.put(
    "/api/v1/menu-items/{menu_item_id}/recipe",
    response_model=ApiResponse[RecipeResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def revise_recipe(
    menu_item_id: MenuItemIdPath,
    body: ReviseRecipeRequestSchema,
    principal: RequireMenuManageDep,
    use_case: ReviseRecipeUseCaseDep,
) -> ApiResponse[RecipeResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        ReviseRecipeRequestDTO(
            menu_item_id=menu_item_id,
            name=body.name,
            ingredients=[
                ReviseRecipeIngredientRequestDTO(
                    inventory_item_id=line.inventory_item_id,
                    quantity=line.quantity,
                    unit=line.unit,
                )
                for line in body.ingredients
            ],
        ),
    )
    return ApiResponse(data=_recipe_to_schema(result))


@router.get(
    "/api/v1/menu-items/{menu_item_id}/recipe",
    response_model=ApiResponse[RecipeResponseSchema],
)
async def get_menu_item_recipe(
    menu_item_id: MenuItemIdPath,
    principal: RequireMenuReadDep,
    use_case: GetMenuItemRecipeUseCaseDep,
) -> ApiResponse[RecipeResponseSchema]:
    result = await use_case.execute(principal.tenant_id, menu_item_id)
    return ApiResponse(data=_recipe_to_schema(result))
