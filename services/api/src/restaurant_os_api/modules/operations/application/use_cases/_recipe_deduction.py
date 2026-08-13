"""Recipe-driven inventory deduction, extracted so
``UpdateKitchenTicketStatusUseCase`` doesn't inline the full
``StockMovement``-construction boilerplate ``RecordStockMovementUseCase``
already established -- mirrors that use case's own discipline exactly
(never write ``InventoryItem.quantity_on_hand`` directly, the
``stock_movements`` trigger owns it; pre-check with ``ensure_not_negative``
purely for a clean typed error, the trigger remains the real
enforcement; re-read the item after insert to decide whether to publish
``LowStockDetected``).

A menu item with no ``recipe_id``, or a recipe with no matching
``RecipeIngredient`` row resolving to a real ``InventoryItem``, is a
silent no-op here, not an error -- not every sellable item has a bill
of materials configured, and refusing to let a kitchen ticket reach
``served`` over a missing recipe would be exactly the kind of invented
business rule this codebase's own convention disclaims.

**Disclosed limitation, inherited from ``ReviseRecipeUseCase``'s own
docstring, not newly introduced here:** ``Recipe`` is tenant-wide but
``RecipeIngredient.inventory_item_id`` points at one fixed, branch-scoped
``InventoryItem`` row. If an order is served at a branch other than the
one that ``InventoryItem`` row actually belongs to, this deduction still
runs -- it writes against whichever branch the recipe's ingredient rows
were configured against, not the serving order's own branch. Real
per-branch recipe accuracy remains out of scope, same as
``ReviseRecipeUseCase`` already discloses.

A caller that hits ``InsufficientStockError`` here means the whole
cascading transaction (kitchen ticket status change and everything it
cascades) rolls back -- deliberately: ``allow_negative_stock``/
``allow_negative_stock_override`` are the existing, real levers a
tenant already has to make sales never block on stock; leaving this
deduction silently permissive regardless of that configuration would
make the toggle meaningless for the one place stock is actually
consumed by a sale.
"""

from __future__ import annotations

from datetime import datetime

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.use_cases._stock_guard import (
    ensure_not_negative,
)
from restaurant_os_api.modules.operations.domain.entities import (
    OrderItem,
    StockMovement,
    StockMovementType,
)
from restaurant_os_api.modules.operations.domain.events import LowStockDetected
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryItemRepository,
    RecipeRepository,
    StockMovementRepository,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, MenuItemRepository
from restaurant_os_api.platform.outbox import OutboxWriter


async def deduct_recipe_inventory_for_served_item(
    *,
    tenant_id: str,
    order_item: OrderItem,
    now: datetime,
    menu_item_repo: MenuItemRepository,
    recipe_repo: RecipeRepository,
    inventory_item_repo: InventoryItemRepository,
    stock_movement_repo: StockMovementRepository,
    branch_repo: BranchRepository,
    outbox: OutboxWriter,
) -> None:
    menu_item = await menu_item_repo.get_by_id(tenant_id, order_item.menu_item_id)
    if menu_item is None or menu_item.recipe_id is None:
        return

    recipe = await recipe_repo.get_by_id(tenant_id, menu_item.recipe_id)
    if recipe is None:
        return

    ingredients = await recipe_repo.list_ingredients_for_recipe(tenant_id, recipe.id)
    for ingredient in ingredients:
        inventory_item = await inventory_item_repo.get_by_id(
            tenant_id, ingredient.inventory_item_id
        )
        if inventory_item is None:
            continue

        branch = await branch_repo.get_by_id(tenant_id, inventory_item.branch_id)
        if branch is None:
            continue

        previous_quantity = inventory_item.quantity_on_hand
        quantity_delta = -(ingredient.quantity * order_item.quantity)
        ensure_not_negative(
            inventory_item,
            branch,
            previous_quantity=previous_quantity,
            quantity_delta=quantity_delta,
        )

        await stock_movement_repo.create_movement(
            StockMovement(
                id=generate_ulid(),
                tenant_id=tenant_id,
                branch_id=inventory_item.branch_id,
                inventory_item_id=inventory_item.id,
                movement_type=StockMovementType.SALE_DEDUCTION,
                quantity_delta=quantity_delta,
                occurred_at=now,
                created_at=now,
                reference_type="order_item",
                reference_id=order_item.id,
            )
        )

        refreshed_item = await inventory_item_repo.get_by_id(tenant_id, inventory_item.id)
        assert refreshed_item is not None
        if (
            refreshed_item.reorder_point is not None
            and previous_quantity > refreshed_item.reorder_point
            and refreshed_item.quantity_on_hand <= refreshed_item.reorder_point
        ):
            await outbox.publish(
                tenant_id,
                LowStockDetected(
                    inventory_item_id=inventory_item.id,
                    branch_id=inventory_item.branch_id,
                    quantity_on_hand=str(refreshed_item.quantity_on_hand),
                    reorder_point=str(refreshed_item.reorder_point),
                    occurred_at=now,
                ),
            )
