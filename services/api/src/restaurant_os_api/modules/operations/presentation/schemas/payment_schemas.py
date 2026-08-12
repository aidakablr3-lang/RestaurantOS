"""Pydantic request/response schemas for Payment/Refund (Sprint 7 Step 4).

``RecordPaymentRequestSchema`` has no ``tip_amount`` field -- a tip is
not part of the restaurant bill (P0 correction, 2026-08-12); the
customer pays exactly the bill's ``amountDue``, nothing more. See
``record_payment.py``'s own docstring for the full business rule.
``PaymentResponseSchema`` still reports ``tip_amount`` (always
``0`` for any payment recorded after this correction) purely for
backward compatibility with any historical rows.

``RequestRefundRequestSchema``/``RefundResponseSchema`` are retained
for the preserved application-layer refund abstraction, but no longer
have a route that uses them -- RestaurantOS v1 does not provide a
customer refund workflow (see ``payment_router.py``'s own docstring
and ``docs/AI_HANDOFF.md``). A payment-provider/bank-side reversal or
dispute is handled entirely outside RestaurantOS.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.operations.domain.entities import TenderType


class RecordPaymentRequestSchema(CamelModel):
    tender_type: TenderType
    amount: Decimal = Field(..., gt=0)
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
