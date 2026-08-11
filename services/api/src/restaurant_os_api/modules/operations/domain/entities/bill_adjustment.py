"""BillAdjustment entity -- append-only, applied once, never edited
(Data Architecture v2.0 Group B unifies tips/discounts/service-charges/
comps/write-offs into one ledger rather than one table per type)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class BillAdjustmentType(StrEnum):
    DISCOUNT = "discount"
    SERVICE_CHARGE = "service_charge"
    TIP = "tip"
    COMP = "comp"
    WRITE_OFF = "write_off"


@dataclass(slots=True)
class BillAdjustment:
    id: str
    tenant_id: str
    bill_id: str
    adjustment_type: BillAdjustmentType
    amount: Decimal
    created_at: datetime
    reference_type: str | None = None
    reference_id: str | None = None
    reason: str | None = None
    approved_by_user_id: str | None = None
