"""Application-layer DTOs for CashDrawer (Sprint 7 Step 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class OpenCashDrawerRequestDTO:
    branch_id: str
    opening_float_amount: Decimal
    terminal_id: str | None = None


@dataclass(frozen=True, slots=True)
class CloseCashDrawerRequestDTO:
    cash_drawer_id: str
    closing_counted_amount: Decimal


@dataclass(frozen=True, slots=True)
class CashDrawerDTO:
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
    # Computed, not stored -- opening_float_amount + settled cash
    # payments since opened. Only populated once the drawer is closed
    # (the reconciliation figure); null while still open.
    expected_cash_amount: Decimal | None = None
    variance_amount: Decimal | None = None
