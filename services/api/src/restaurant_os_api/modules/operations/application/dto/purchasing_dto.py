"""Application-layer DTOs for Supplier + PurchaseOrder + PurchaseOrderItem
+ GoodsReceipt (Sprint 7 Step 6). Reuses the restaurant module's own
``AddressRequestDTO``/``AddressDTO`` rather than duplicating them --
Supplier's address is the same reused Address shape Branch already
uses (Architecture doc SS3.7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from restaurant_os_api.modules.restaurant.application.dto import AddressDTO, AddressRequestDTO


@dataclass(frozen=True, slots=True)
class CreateSupplierRequestDTO:
    name: str
    address: AddressRequestDTO | None = None


@dataclass(frozen=True, slots=True)
class UpdateSupplierRequestDTO:
    supplier_id: str
    name: str
    status: str
    address: AddressRequestDTO | None = None


@dataclass(frozen=True, slots=True)
class SupplierDTO:
    id: str
    tenant_id: str
    name: str
    status: str
    created_at: datetime
    address: AddressDTO | None


@dataclass(frozen=True, slots=True)
class SupplierListResultDTO:
    suppliers: list[SupplierDTO]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class CreatePurchaseOrderRequestDTO:
    branch_id: str
    supplier_id: str


@dataclass(frozen=True, slots=True)
class AddPurchaseOrderItemRequestDTO:
    purchase_order_id: str
    inventory_item_id: str
    quantity_ordered: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseOrderItemDTO:
    id: str
    purchase_order_id: str
    inventory_item_id: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PurchaseOrderDTO:
    id: str
    tenant_id: str
    branch_id: str
    supplier_id: str
    status: str
    created_at: datetime
    items: list[PurchaseOrderItemDTO]


@dataclass(frozen=True, slots=True)
class PurchaseOrderListResultDTO:
    purchase_orders: list[PurchaseOrderDTO]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class ConfirmGoodsReceiptLineRequestDTO:
    purchase_order_item_id: str
    quantity_received: Decimal


@dataclass(frozen=True, slots=True)
class ConfirmGoodsReceiptRequestDTO:
    purchase_order_id: str
    lines: list[ConfirmGoodsReceiptLineRequestDTO] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GoodsReceiptDTO:
    id: str
    tenant_id: str
    purchase_order_id: str
    status: str
    received_at: datetime
    created_at: datetime
    has_discrepancy: bool
    purchase_order: PurchaseOrderDTO
