"""Application-layer DTOs for Bill/BillAdjustment/OrderTaxLine (Sprint 7
Step 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class GenerateBillRequestDTO:
    order_id: str


@dataclass(frozen=True, slots=True)
class ApplyBillAdjustmentRequestDTO:
    bill_id: str
    adjustment_type: str
    amount: Decimal | None = None
    discount_id: str | None = None
    reason: str | None = None
    approved_by_user_id: str | None = None


@dataclass(frozen=True, slots=True)
class OrderTaxLineDTO:
    id: str
    order_id: str
    tax_id: str
    taxable_amount: Decimal
    tax_rate_snapshot: Decimal
    tax_amount: Decimal
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BillAdjustmentDTO:
    id: str
    bill_id: str
    adjustment_type: str
    amount: Decimal
    created_at: datetime
    reference_type: str | None
    reference_id: str | None
    reason: str | None
    approved_by_user_id: str | None


@dataclass(frozen=True, slots=True)
class BillDTO:
    id: str
    tenant_id: str
    branch_id: str
    status: str
    created_at: datetime
    order_id: str | None
    tab_id: str | None
    subtotal_amount: Decimal
    tax_amount: Decimal
    adjustments_total: Decimal
    amount_due: Decimal
    amount_paid: Decimal
    tax_lines: list[OrderTaxLineDTO]
    adjustments: list[BillAdjustmentDTO]
    invoice_number: str | None = None
