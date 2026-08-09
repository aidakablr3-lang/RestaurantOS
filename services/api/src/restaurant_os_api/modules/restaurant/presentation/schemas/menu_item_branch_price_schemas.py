"""Pydantic request/response schemas for MenuItemBranchPrice (Sprint 5
Step 4.10).

``branch_id`` arrives in the body, not the URL path -- the route is
flat (``PUT``/``GET /api/v1/menu-items/{menu_item_id}/branch-price``),
the same shape ``ChangeTableStatusUseCase`` already established for a
flat action route with no ``branch_id`` in the URL to authorize
against. Cross-field ``effectiveFrom < effectiveTo`` validation
mirrors ``OperatingHoursEntryRequestSchema``'s own
``opensAt < closesAt`` precedent -- the database's own
``CHECK (effective_from < effective_to OR effective_to IS NULL)``
constraint (migration 0004) is the authoritative enforcement; this is
a fast, user-facing 422 in front of it.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from restaurant_os_api.core.response import CamelModel


class CreateMenuItemBranchPriceRequestSchema(CamelModel):
    branch_id: str = Field(..., min_length=26, max_length=26)
    price_amount: Decimal = Field(..., ge=0)
    effective_from: datetime
    effective_to: datetime | None = None

    @model_validator(mode="after")
    def _check_effective_window(self) -> CreateMenuItemBranchPriceRequestSchema:
        if self.effective_to is not None and self.effective_from >= self.effective_to:
            raise ValueError("effectiveFrom must be before effectiveTo")
        return self


class MenuItemBranchPriceResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    menu_item_id: str
    price_amount: Decimal
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
