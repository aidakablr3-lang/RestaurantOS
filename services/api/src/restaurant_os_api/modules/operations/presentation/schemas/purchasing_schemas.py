"""Pydantic request/response schemas for Supplier + PurchaseOrder +
PurchaseOrderItem + GoodsReceipt (Sprint 7 Step 6). Reuses the
restaurant module's own ``AddressRequestSchema``/``AddressResponseSchema``
directly rather than duplicating them -- Supplier's address is the
same reused Address shape Branch already uses."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.restaurant.presentation.schemas.branch_schemas import (
    AddressRequestSchema,
    AddressResponseSchema,
)

SupplierStatusLiteral = Literal["active", "inactive"]


class CreateSupplierRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: AddressRequestSchema | None = None


class UpdateSupplierRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    status: SupplierStatusLiteral
    address: AddressRequestSchema | None = None


class SupplierResponseSchema(CamelModel):
    id: str
    tenant_id: str
    name: str
    status: str
    created_at: datetime
    address: AddressResponseSchema | None


class CreatePurchaseOrderRequestSchema(CamelModel):
    supplier_id: str = Field(..., min_length=26, max_length=26)


class AddPurchaseOrderItemRequestSchema(CamelModel):
    inventory_item_id: str = Field(..., min_length=26, max_length=26)
    quantity_ordered: Decimal = Field(..., gt=0)


class PurchaseOrderItemResponseSchema(CamelModel):
    id: str
    purchase_order_id: str
    inventory_item_id: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    created_at: datetime


class PurchaseOrderResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    supplier_id: str
    status: str
    created_at: datetime
    items: list[PurchaseOrderItemResponseSchema]


class ConfirmGoodsReceiptLineRequestSchema(CamelModel):
    purchase_order_item_id: str = Field(..., min_length=26, max_length=26)
    quantity_received: Decimal = Field(..., gt=0)


class ConfirmGoodsReceiptRequestSchema(CamelModel):
    lines: list[ConfirmGoodsReceiptLineRequestSchema] = Field(..., min_length=1)


class GoodsReceiptResponseSchema(CamelModel):
    id: str
    tenant_id: str
    purchase_order_id: str
    status: str
    received_at: datetime
    created_at: datetime
    has_discrepancy: bool
    purchase_order: PurchaseOrderResponseSchema
