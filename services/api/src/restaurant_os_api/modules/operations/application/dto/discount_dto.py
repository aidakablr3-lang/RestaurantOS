"""Application-layer DTOs for Discount (Sprint 7 Step 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreateDiscountRequestDTO:
    name: str
    discount_type: str
    value: Decimal
    requires_approval: bool = False
    max_value: Decimal | None = None
    active_from: datetime | None = None
    active_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class DiscountDTO:
    id: str
    tenant_id: str
    name: str
    discount_type: str
    value: Decimal
    requires_approval: bool
    created_at: datetime
    max_value: Decimal | None
    active_from: datetime | None
    active_to: datetime | None


@dataclass(frozen=True, slots=True)
class DiscountListResultDTO:
    discounts: list[DiscountDTO]
    total: int
    offset: int
    limit: int
