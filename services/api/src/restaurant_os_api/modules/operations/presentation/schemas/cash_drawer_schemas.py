"""Pydantic request/response schemas for CashDrawer (Sprint 7 Step 4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class OpenCashDrawerRequestSchema(CamelModel):
    opening_float_amount: Decimal = Field(..., ge=0)
    terminal_id: str | None = None


class CloseCashDrawerRequestSchema(CamelModel):
    closing_counted_amount: Decimal = Field(..., ge=0)


class CashDrawerResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    status: str
    opening_float_amount: Decimal
    opened_at: datetime
    created_at: datetime
    terminal_id: str | None
    closing_counted_amount: Decimal | None
    closed_at: datetime | None
    expected_cash_amount: Decimal | None
    variance_amount: Decimal | None
