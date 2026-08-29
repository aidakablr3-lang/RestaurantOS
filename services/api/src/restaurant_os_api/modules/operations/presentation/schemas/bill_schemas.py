"""Pydantic request/response schemas for Bill/BillAdjustment/OrderTaxLine/Tax
(Sprint 7 Step 4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.operations.domain.entities import BillAdjustmentType


class ApplyBillAdjustmentRequestSchema(CamelModel):
    adjustment_type: BillAdjustmentType
    amount: Decimal | None = None
    discount_id: str | None = Field(default=None, min_length=26, max_length=26)
    reason: str | None = None
    approved_by_user_id: str | None = Field(default=None, min_length=26, max_length=26)


class CreateTaxRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    # A fraction (0.09 for 9%), not a percent -- ge=0.5 upper bound is a
    # plausibility guard, not a real-world ceiling: no restaurant tax
    # rate is ever above 50%, so anything higher is almost certainly a
    # percent value that wasn't converted (or was converted by /10
    # instead of /100). See CreateTaxUseCase for the matching
    # defense-in-depth check on the onboarding entry point, which has no
    # Pydantic schema of its own.
    rate: Decimal = Field(..., ge=0, le=Decimal("0.5"))


class OrderTaxLineResponseSchema(CamelModel):
    id: str
    order_id: str
    tax_id: str
    taxable_amount: Decimal
    tax_rate_snapshot: Decimal
    tax_amount: Decimal
    created_at: datetime


class BillAdjustmentResponseSchema(CamelModel):
    id: str
    bill_id: str
    adjustment_type: str
    amount: Decimal
    created_at: datetime
    reference_type: str | None
    reference_id: str | None
    reason: str | None
    approved_by_user_id: str | None


class BillResponseSchema(CamelModel):
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
    tax_lines: list[OrderTaxLineResponseSchema]
    adjustments: list[BillAdjustmentResponseSchema]
    invoice_number: str | None = None


class TaxResponseSchema(CamelModel):
    id: str
    tenant_id: str
    name: str
    rate: Decimal
    is_active: bool
    created_at: datetime
