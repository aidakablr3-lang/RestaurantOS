"""Application-layer DTOs for Payment/Refund (Sprint 7 Step 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RecordPaymentRequestDTO:
    bill_id: str
    tender_type: str
    amount: Decimal
    tip_amount: Decimal = Decimal(0)
    gateway_token_ref: str | None = None
    gateway_last4: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentDTO:
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


@dataclass(frozen=True, slots=True)
class RequestRefundRequestDTO:
    payment_id: str
    approved_by_user_id: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class RefundDTO:
    id: str
    tenant_id: str
    branch_id: str
    payment_id: str
    order_id: str
    approved_by_user_id: str
    amount: Decimal
    status: str
    created_at: datetime
