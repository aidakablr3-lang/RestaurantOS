"""Pydantic request/response schemas for MenuItemAvailability (Sprint 5
Step 4.10) -- the availability-dimension twin of
``menu_item_branch_price_schemas.py`` (see that module's own docstring
for the full reasoning behind the flat route shape and the
cross-field validation).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from restaurant_os_api.core.response import CamelModel


class CreateMenuItemAvailabilityRequestSchema(CamelModel):
    branch_id: str = Field(..., min_length=26, max_length=26)
    is_available: bool
    effective_from: datetime
    effective_to: datetime | None = None

    @model_validator(mode="after")
    def _check_effective_window(self) -> CreateMenuItemAvailabilityRequestSchema:
        if self.effective_to is not None and self.effective_from >= self.effective_to:
            raise ValueError("effectiveFrom must be before effectiveTo")
        return self


class MenuItemAvailabilityResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    menu_item_id: str
    is_available: bool
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
