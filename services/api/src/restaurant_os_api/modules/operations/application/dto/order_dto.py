"""Application-layer DTOs for Order/OrderItem (Sprint 7 Step 3).

``customer_id`` is never settable from a request DTO -- ``Customer``
doesn't exist yet, the same reserved-but-inert shape
``CreateReservationRequestDTO`` already established for the same reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class CreateOrderRequestDTO:
    branch_id: str
    order_source: str
    table_id: str | None = None
    tab_id: str | None = None
    origin_device_id: str | None = None


@dataclass(frozen=True, slots=True)
class AddOrderItemRequestDTO:
    order_id: str
    menu_item_id: str
    quantity: int
    modifiers_snapshot: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class OrderItemDTO:
    id: str
    order_id: str
    menu_item_id: str
    quantity: int
    unit_price_amount: Decimal
    line_status: str
    created_at: datetime
    modifiers_snapshot: list[dict[str, Any]]
    recipe_cost_snapshot: Decimal | None


@dataclass(frozen=True, slots=True)
class OrderDTO:
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
    items: list[OrderItemDTO]
    table_id: str | None
    tab_id: str | None
    customer_id: str | None
    closed_at: datetime | None
    origin_device_id: str | None


@dataclass(frozen=True, slots=True)
class OrderListResultDTO:
    orders: list[OrderDTO]
    total: int
    offset: int
    limit: int
