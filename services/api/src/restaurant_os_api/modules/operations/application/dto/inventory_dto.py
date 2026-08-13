"""Application-layer DTOs for InventoryCategory + InventoryItem +
StockMovement (Sprint 7 Step 5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreateInventoryCategoryRequestDTO:
    name: str


@dataclass(frozen=True, slots=True)
class InventoryCategoryDTO:
    id: str
    tenant_id: str
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class InventoryCategoryListResultDTO:
    categories: list[InventoryCategoryDTO]


@dataclass(frozen=True, slots=True)
class CreateInventoryItemRequestDTO:
    branch_id: str
    inventory_category_id: str
    name: str
    unit: str
    reorder_point: Decimal | None = None
    allow_negative_stock_override: bool | None = None


@dataclass(frozen=True, slots=True)
class UpdateInventoryItemRequestDTO:
    """Full-replace PATCH, matching ``UpdateMenuItemRequestDTO``'s own
    shape -- every editable field is required on the request, so
    clearing a nullable field is just passing ``None`` for it rather
    than needing a separate "was this field provided" sentinel."""

    inventory_item_id: str
    inventory_category_id: str
    name: str
    reorder_point: Decimal | None
    allow_negative_stock_override: bool | None


@dataclass(frozen=True, slots=True)
class InventoryItemDTO:
    id: str
    tenant_id: str
    branch_id: str
    inventory_category_id: str
    name: str
    unit: str
    quantity_on_hand: Decimal
    created_at: datetime
    reorder_point: Decimal | None
    allow_negative_stock_override: bool | None


@dataclass(frozen=True, slots=True)
class InventoryItemListResultDTO:
    items: list[InventoryItemDTO]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class RecordStockMovementRequestDTO:
    inventory_item_id: str
    movement_type: str
    quantity_delta: Decimal
    reason: str | None = None
    approved_by_user_id: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None


@dataclass(frozen=True, slots=True)
class StockMovementDTO:
    id: str
    tenant_id: str
    branch_id: str
    inventory_item_id: str
    movement_type: str
    quantity_delta: Decimal
    occurred_at: datetime
    created_at: datetime
    reference_type: str | None
    reference_id: str | None
    idempotency_key: str | None


@dataclass(frozen=True, slots=True)
class StockMovementListResultDTO:
    movements: list[StockMovementDTO]
    total: int
    offset: int
    limit: int
