"""Pydantic request/response schemas for InventoryCategory + InventoryItem
+ StockMovement (Sprint 7 Step 5)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class CreateInventoryCategoryRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)


class InventoryCategoryResponseSchema(CamelModel):
    id: str
    tenant_id: str
    name: str
    created_at: datetime


class CreateInventoryItemRequestSchema(CamelModel):
    inventory_category_id: str = Field(..., min_length=26, max_length=26)
    name: str = Field(..., min_length=1, max_length=255)
    unit: str = Field(..., min_length=1, max_length=50)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    allow_negative_stock_override: bool | None = None


class UpdateInventoryItemRequestSchema(CamelModel):
    inventory_category_id: str = Field(..., min_length=26, max_length=26)
    name: str = Field(..., min_length=1, max_length=255)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    allow_negative_stock_override: bool | None = None


class InventoryItemResponseSchema(CamelModel):
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


# Deliberately excludes 'sale_deduction' (system-internal, never a
# direct client-facing POST) and 'receipt' (Step 6 Purchasing's own
# GoodsReceipt-confirmation concern) -- see RecordStockMovementUseCase's
# own docstring.
ClientWritableMovementType = Literal["adjustment", "waste", "transfer"]


class RecordStockMovementRequestSchema(CamelModel):
    movement_type: ClientWritableMovementType
    # Zero-delta rejection is enforced by the DB's own
    # ``quantity_delta_is_nonzero`` CHECK constraint (Pydantic's Field
    # has no ``ne`` constraint to mirror it at this layer).
    quantity_delta: Decimal
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    approved_by_user_id: str | None = Field(default=None, min_length=26, max_length=26)
    reference_type: str | None = Field(default=None, max_length=100)
    reference_id: str | None = Field(default=None, min_length=26, max_length=26)


class StockMovementResponseSchema(CamelModel):
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
