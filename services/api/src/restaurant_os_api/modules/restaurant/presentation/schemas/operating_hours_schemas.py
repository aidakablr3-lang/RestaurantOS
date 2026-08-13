"""Pydantic request/response schemas for Operating Hours.

Per-row validation lives here (day range, closed/open+times
consistency, opens < closes) -- the same layering
``CreateRestaurantRequestSchema`` already uses for its own field
constraints. Cross-row validation (overlap, closed-vs-open conflict
for the same day) cannot be expressed on a single row and lives in
``ReplaceOperatingHoursUseCase`` instead (Architecture SS3.1: "overlap
validation is an application-layer concern, not a schema constraint").
"""

from __future__ import annotations

from datetime import time

from pydantic import Field, model_validator

from restaurant_os_api.core.response import CamelModel


class OperatingHoursEntryRequestSchema(CamelModel):
    day_of_week: int = Field(..., ge=0, le=6)
    is_closed: bool = False
    opens_at: time | None = None
    closes_at: time | None = None

    @model_validator(mode="after")
    def _check_open_entry_has_valid_times(self) -> OperatingHoursEntryRequestSchema:
        if not self.is_closed:
            if self.opens_at is None or self.closes_at is None:
                raise ValueError("an open entry requires both opensAt and closesAt")
            if self.opens_at >= self.closes_at:
                raise ValueError("opensAt must be before closesAt")
        return self


class ReplaceOperatingHoursRequestSchema(CamelModel):
    entries: list[OperatingHoursEntryRequestSchema] = Field(default_factory=list)


class OperatingHoursEntryResponseSchema(CamelModel):
    id: str
    day_of_week: int
    is_closed: bool
    opens_at: time | None
    closes_at: time | None
