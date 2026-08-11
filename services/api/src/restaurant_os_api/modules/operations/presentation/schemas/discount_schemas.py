"""Pydantic request/response schemas for Discount (Sprint 7 Step 4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.operations.domain.entities import DiscountType


class CreateDiscountRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    discount_type: DiscountType
    value: Decimal = Field(..., ge=0)
    requires_approval: bool = False
    max_value: Decimal | None = Field(default=None, ge=0)
    active_from: datetime | None = None
    active_to: datetime | None = None


class DiscountResponseSchema(CamelModel):
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
