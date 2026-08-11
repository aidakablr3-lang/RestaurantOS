from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import (
    InventoryCategoryDTO,
    InventoryItemDTO,
    StockMovementDTO,
)
from restaurant_os_api.modules.operations.domain.entities import (
    InventoryCategory,
    InventoryItem,
    StockMovement,
)


def inventory_category_to_dto(category: InventoryCategory) -> InventoryCategoryDTO:
    return InventoryCategoryDTO(
        id=category.id,
        tenant_id=category.tenant_id,
        name=category.name,
        created_at=category.created_at,
    )


def inventory_item_to_dto(item: InventoryItem) -> InventoryItemDTO:
    return InventoryItemDTO(
        id=item.id,
        tenant_id=item.tenant_id,
        branch_id=item.branch_id,
        inventory_category_id=item.inventory_category_id,
        name=item.name,
        unit=item.unit,
        quantity_on_hand=item.quantity_on_hand,
        created_at=item.created_at,
        reorder_point=item.reorder_point,
        allow_negative_stock_override=item.allow_negative_stock_override,
    )


def stock_movement_to_dto(movement: StockMovement) -> StockMovementDTO:
    return StockMovementDTO(
        id=movement.id,
        tenant_id=movement.tenant_id,
        branch_id=movement.branch_id,
        inventory_item_id=movement.inventory_item_id,
        movement_type=movement.movement_type.value,
        quantity_delta=movement.quantity_delta,
        occurred_at=movement.occurred_at,
        created_at=movement.created_at,
        reference_type=movement.reference_type,
        reference_id=movement.reference_id,
        idempotency_key=movement.idempotency_key,
    )
