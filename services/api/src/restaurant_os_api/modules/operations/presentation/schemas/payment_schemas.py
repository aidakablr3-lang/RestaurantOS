"""Pydantic request/response schemas for Payment/Refund (Sprint 7 Step 4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.operations.domain.entities import TenderType


class RecordPaymentRequestSchema(CamelModel):
    tender_type: TenderType
    amount: Decimal = Field(..., gt=0)
    tip_amount: Decimal = Field(default=Decimal(0), ge=0)
    gateway_token_ref: str | None = None
    gateway_last4: str | None = Field(default=None, max_length=4)


class PaymentResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    bill_id: str
    tender_type: str
    amount: Decimal
    currency_code: str
    tip_amount: Decimal
    status: str
    created_at: datetime
    gateway_token_ref: str | None
    gateway_last4: str | None


class RequestRefundRequestSchema(CamelModel):
    approved_by_user_id: str = Field(..., min_length=26, max_length=26)
    amount: Decimal = Field(..., gt=0)


class RefundResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    payment_id: str
    order_id: str
    approved_by_user_id: str
    amount: Decimal
    status: str
    created_at: datetime
