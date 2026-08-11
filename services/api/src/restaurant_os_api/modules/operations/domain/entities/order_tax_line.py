"""OrderTaxLine entity -- append-only, written once at bill generation
(Data Architecture v2.0 Group C). One row per distinct order x tax
rate, with the rate snapshotted so a later change to a Tax's own rate
never retroactively changes a historical bill's numbers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class OrderTaxLine:
    id: str
    tenant_id: str
    order_id: str
    tax_id: str
    taxable_amount: Decimal
    tax_rate_snapshot: Decimal
    tax_amount: Decimal
    created_at: datetime
