"""Pydantic request/response schemas for Order/OrderItem (Sprint 7 Step 3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.operations.domain.entities import OrderSource


class CreateOrderRequestSchema(CamelModel):
    order_source: OrderSource
    table_id: str | None = Field(default=None, min_length=26, max_length=26)
    tab_id: str | None = Field(default=None, min_length=26, max_length=26)
    origin_device_id: str | None = None


class AddOrderItemRequestSchema(CamelModel):
    menu_item_id: str = Field(..., min_length=26, max_length=26)
    quantity: int = Field(..., gt=0)
    modifiers_snapshot: list[dict[str, Any]] = Field(default_factory=list)


class OrderItemResponseSchema(CamelModel):
    id: str
    order_id: str
    menu_item_id: str
    quantity: int
    unit_price_amount: Decimal
    line_status: str
    created_at: datetime
    modifiers_snapshot: list[dict[str, Any]]
    recipe_cost_snapshot: Decimal | None


class OrderResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    order_source: str
    status: str
    subtotal_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency_code: str
    opened_at: datetime
    created_at: datetime
    items: list[OrderItemResponseSchema]
    table_id: str | None
    tab_id: str | None
    customer_id: str | None
    closed_at: datetime | None
    origin_device_id: str | None
