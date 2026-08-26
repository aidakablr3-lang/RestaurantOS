"""AddRecipesStep -- Phase 1 design doc §A.7, with the same deliberate
scope expansion as ``AddInventoryStep`` (§A.7 scoped this row as
"registry node only... same reason [as add_inventory]"; per an
explicit follow-up instruction overriding that deferral, this step
ships a real, single-recipe ``execute``/``verify``, not a bulk
importer).

``requires=[create_menu_items, add_inventory]`` -- both a menu item to
attach the recipe to and an inventory item to use as an ingredient
must already exist. ``ReviseRecipeUseCase`` is both "create" and
"revise" (there is no separate bare-recipe-creation use case in this
codebase -- see the use case's own docstring); this step always calls
it with exactly one ingredient line, built from ``ctx.inventory_item_id``
(the one item ``AddInventoryStep`` created).

The operator picks *which* of ``ctx.menu_item_ids`` gets the recipe
via ``input.menu_item_id`` -- ``autofill()`` offers the first one
created as a default, since nothing in ``ctx`` singles one out
otherwise.

``verify()`` reads the recipe back via ``GetMenuItemRecipeUseCase``,
keyed by ``ctx.recipe_menu_item_id`` (the menu item this step attached
a recipe to) rather than by recipe id -- matching that use case's own
signature, and naturally catching both "the recipe row is gone" and
"the menu item's ``recipe_id`` was unset" as the same
``RecipeNotFoundError``.

``execute()`` writes two kinds of records -- the ``Recipe`` row itself
and its ``RecipeIngredient`` row(s) -- so ``verify()`` checks both:
the recipe read-back already includes ``ingredients`` (``GetMenuItemRecipeUseCase``
calls ``recipe_repo.list_ingredients_for_recipe`` internally), and
``verify()`` asserts that list is non-empty *and* still references
``ctx.inventory_item_id`` specifically -- a recipe row that survived
with its one ingredient row deleted out from under it (recipe and
ingredient are separate tables) must fail, not pass on the strength of
the parent row alone.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)
from restaurant_os_api.modules.operations.application.dto import (
    RecipeDTO,
    ReviseRecipeIngredientRequestDTO,
    ReviseRecipeRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases.get_menu_item_recipe import (
    GetMenuItemRecipeUseCase,
)
from restaurant_os_api.modules.operations.application.use_cases.revise_recipe import (
    ReviseRecipeUseCase,
)
from restaurant_os_api.modules.operations.domain.exceptions import RecipeNotFoundError


class AddRecipesStepInput(BaseModel):
    menu_item_id: str
    name: str
    quantity: Decimal
    unit: str


class AddRecipesStep:
    def __init__(
        self,
        *,
        revise_recipe_use_case: ReviseRecipeUseCase,
        get_menu_item_recipe_use_case: GetMenuItemRecipeUseCase,
    ) -> None:
        self.id = StepId.ADD_RECIPES
        self.title = "Add recipe"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_MENU_ITEMS, StepId.ADD_INVENTORY)
        self.collect_schema = AddRecipesStepInput
        self.autonomous = False

        self._revise_recipe_use_case = revise_recipe_use_case
        self._get_menu_item_recipe_use_case = get_menu_item_recipe_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        if ctx.menu_item_ids:
            return {"menu_item_id": ctx.menu_item_ids[0]}
        return {}

    async def execute(self, input: AddRecipesStepInput, ctx: OnboardingRunContext) -> RecipeDTO:
        assert ctx.tenant_id is not None and ctx.inventory_item_id is not None, (
            "add_recipes requires create_menu_items and add_inventory first"
        )
        return await self._revise_recipe_use_case.execute(
            ctx.tenant_id,
            ReviseRecipeRequestDTO(
                menu_item_id=input.menu_item_id,
                name=input.name,
                ingredients=[
                    ReviseRecipeIngredientRequestDTO(
                        inventory_item_id=ctx.inventory_item_id,
                        quantity=input.quantity,
                        unit=input.unit,
                    )
                ],
            ),
        )

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.recipe_menu_item_id is None:
            return VerifyFailure(reason="tenant_id/recipe_menu_item_id not yet in context")
        try:
            recipe = await self._get_menu_item_recipe_use_case.execute(
                ctx.tenant_id, ctx.recipe_menu_item_id
            )
        except RecipeNotFoundError:
            return VerifyFailure(
                reason=f"recipe for menu item {ctx.recipe_menu_item_id} not found on read-back"
            )

        if not recipe.ingredients:
            return VerifyFailure(
                reason=f"recipe {recipe.id} for menu item {ctx.recipe_menu_item_id} has no ingredients"
            )

        if ctx.inventory_item_id is not None and not any(
            ing.inventory_item_id == ctx.inventory_item_id for ing in recipe.ingredients
        ):
            return VerifyFailure(
                reason=(
                    f"recipe {recipe.id} for menu item {ctx.recipe_menu_item_id} no longer "
                    f"references inventory item {ctx.inventory_item_id}"
                )
            )

        return VerifySuccess(
            evidence=(
                f"GET recipe for menu item {ctx.recipe_menu_item_id} -> "
                f"version={recipe.version}, {len(recipe.ingredients)} ingredient(s)"
            )
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "AddRecipesStep.undo() is not implemented in Phase 1 -- no caller abandons a run yet."
        )
