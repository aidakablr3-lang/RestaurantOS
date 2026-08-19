"""Integration tests for the Catalog track -- ``CreateMenuCategoryStep``,
``CreateMenuItemsStep``, ``AddInventoryStep``, ``AddRecipesStep`` (Phase
1 design doc SSA.7) -- against real Postgres.

``CreateMenuCategoryStep`` is tested off ``restaurant_ctx`` specifically
(not ``branch_ctx``), proving the design doc's own claim that this step
is restaurant-scoped, not branch-scoped -- ``requires=[create_restaurant]``,
deliberately one level shallower than the Catalog track's other steps.

``CreateMenuItemsStep`` creates two items and soft-deletes only one,
proving partial loss is caught.

``AddRecipesStep`` needs both a menu item and an inventory item
(``requires=[create_menu_items, add_inventory]``) -- built via the
shared ``catalog_with_inventory_ctx`` fixture, which really executes
both prerequisite steps first.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from restaurant_os_api.modules.onboarding.application.steps.add_inventory_step import (
    AddInventoryStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.add_recipes_step import (
    AddRecipesStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_menu_category_step import (
    CreateMenuCategoryStepInput,
)
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifySuccess,
)

from .conftest import (
    make_add_inventory_step,
    make_add_recipes_step,
    make_create_menu_category_step,
    make_create_menu_items_step,
)


async def test_create_menu_category_step_verify_detects_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    restaurant_ctx: OnboardingRunContext,
) -> None:
    step = make_create_menu_category_step(session_factory)

    category = await step.execute(CreateMenuCategoryStepInput(name="Desserts"), restaurant_ctx)
    ctx = restaurant_ctx.model_copy(update={"menu_category_id": category.id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE menu_categories SET deleted_at = now() WHERE id = :id"),
            {"id": category.id},
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert category.id in result_after_delete.reason
    assert "menu category" in result_after_delete.reason


async def test_create_menu_items_step_verify_detects_partial_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    menu_items_ctx: OnboardingRunContext,
) -> None:
    """``menu_items_ctx`` already executed ``CreateMenuItemsStep`` for
    real (two items: Burger, Fries) -- this test re-verifies with a
    freshly-built step instance, then soft-deletes only one item."""
    items_step = make_create_menu_items_step(session_factory)

    result = await items_step.verify(menu_items_ctx)
    assert isinstance(result, VerifySuccess)

    second_item_id = menu_items_ctx.menu_item_ids[1]
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE menu_items SET deleted_at = now() WHERE id = :id"),
            {"id": second_item_id},
        )

    result_after_delete = await items_step.verify(menu_items_ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    first_item_id = menu_items_ctx.menu_item_ids[0]
    assert second_item_id in result_after_delete.reason
    assert first_item_id not in result_after_delete.reason
    assert "menu item" in result_after_delete.reason


async def test_add_inventory_step_verify_detects_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    branch_ctx: OnboardingRunContext,
) -> None:
    step = make_add_inventory_step(session_factory)

    item = await step.execute(
        AddInventoryStepInput(
            category_name="Bar Stock", category_type="beverage", item_name="Vodka", unit="bottle"
        ),
        branch_ctx,
    )
    ctx = branch_ctx.model_copy(update={"inventory_item_id": item.id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE inventory_items SET deleted_at = now() WHERE id = :id"), {"id": item.id}
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert item.id in result_after_delete.reason
    assert "inventory item" in result_after_delete.reason


async def test_add_inventory_step_verify_detects_category_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    branch_ctx: OnboardingRunContext,
) -> None:
    """The item itself is untouched -- only its *category* is
    soft-deleted. ``GetInventoryItemUseCase`` alone would not catch
    this (it only reads the category for a permission gate, never
    checks it still exists); ``AddInventoryStep.verify()`` must
    independently re-check the category via ``GetInventoryCategoryUseCase``."""
    step = make_add_inventory_step(session_factory)

    item = await step.execute(
        AddInventoryStepInput(
            category_name="Produce Two", category_type="beverage", item_name="Lime", unit="each"
        ),
        branch_ctx,
    )
    ctx = branch_ctx.model_copy(update={"inventory_item_id": item.id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE inventory_categories SET deleted_at = now() WHERE id = :id"),
            {"id": item.inventory_category_id},
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert item.inventory_category_id in result_after_delete.reason
    assert "category" in result_after_delete.reason


async def test_add_recipes_step_verify_detects_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    catalog_with_inventory_ctx: OnboardingRunContext,
) -> None:
    step = make_add_recipes_step(session_factory)
    menu_item_id = catalog_with_inventory_ctx.menu_item_ids[0]

    recipe = await step.execute(
        AddRecipesStepInput(
            menu_item_id=menu_item_id, name="Burger Recipe", quantity=Decimal("0.2"), unit="kg"
        ),
        catalog_with_inventory_ctx,
    )
    ctx = catalog_with_inventory_ctx.model_copy(update={"recipe_menu_item_id": menu_item_id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE recipes SET deleted_at = now() WHERE id = :id"), {"id": recipe.id}
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert menu_item_id in result_after_delete.reason
    assert "recipe" in result_after_delete.reason


async def test_add_recipes_step_verify_detects_ingredient_only_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    catalog_with_inventory_ctx: OnboardingRunContext,
) -> None:
    """The recipe row itself survives untouched -- only its one
    ``RecipeIngredient`` row (a separate table) is removed.
    ``recipe_ingredients`` has no ``deleted_at`` column at all
    (``RecipeIngredientModel`` doesn't inherit ``SoftDeleteMixin`` --
    recipes are immutable/versioned, so there's no production path that
    edits one in place; a hard ``DELETE`` is the only way to simulate
    "gone" for this table, unlike every other entity in this suite).
    ``GetMenuItemRecipeUseCase`` alone would still return the recipe
    (empty ``ingredients`` list); ``verify()`` must reject that, not
    just check the parent row exists."""
    step = make_add_recipes_step(session_factory)
    menu_item_id = catalog_with_inventory_ctx.menu_item_ids[0]

    recipe = await step.execute(
        AddRecipesStepInput(
            menu_item_id=menu_item_id, name="Burger Recipe", quantity=Decimal("0.2"), unit="kg"
        ),
        catalog_with_inventory_ctx,
    )
    ctx = catalog_with_inventory_ctx.model_copy(update={"recipe_menu_item_id": menu_item_id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM recipe_ingredients WHERE recipe_id = :id"), {"id": recipe.id}
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert recipe.id in result_after_delete.reason
