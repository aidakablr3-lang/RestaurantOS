"""Discount entity -- a manager-configured discount catalog (e.g.
"Staff meal -- 50%", "Happy hour -- 20%"). Tenant-scoped reference
data; no lifecycle beyond soft-delete (retired via ``deleted_at``,
handled at the repository layer like every other soft-deletable entity
in this codebase)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class DiscountType(StrEnum):
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"


@dataclass(slots=True)
class Discount:
    id: str
    tenant_id: str
    name: str
    discount_type: DiscountType
    value: Decimal
    requires_approval: bool
    created_at: datetime
    max_value: Decimal | None = None
    active_from: datetime | None = None
    active_to: datetime | None = None

    def compute_amount(self, base_amount: Decimal) -> Decimal:
        """The adjustment amount this discount produces against a given
        base (e.g. the order subtotal). Percentage discounts are capped
        by ``max_value`` when set; fixed-amount discounts never exceed
        the base itself (a fixed discount larger than the bill would
        otherwise produce a negative bill total)."""
        if self.discount_type == DiscountType.PERCENTAGE:
            amount = base_amount * (self.value / Decimal(100))
            if self.max_value is not None:
                amount = min(amount, self.max_value)
            return amount
        return min(self.value, base_amount)
