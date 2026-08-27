"""Pydantic request/response schemas for Operating Hours.

Per-row validation lives here (day range, closed/open+times
consistency) -- the same layering ``CreateRestaurantRequestSchema``
already uses for its own field constraints. Cross-row validation
(overlap, closed-vs-open conflict for the same day) cannot be
expressed on a single row and lives in ``ReplaceOperatingHoursUseCase``
instead (Architecture SS3.1: "overlap validation is an
application-layer concern, not a schema constraint").

``opensAt``/``closesAt`` are bare times of day, no date component.
``closesAt < opensAt`` is a legitimate overnight window -- closing on
the *following* calendar day (e.g. opens 22:00, closes 02:00) -- not
an error; every bar/pub open past midnight needs exactly this shape.
The only genuinely invalid same-day-open input is ``opensAt ==
closesAt`` (a zero-length window). See
``ReplaceOperatingHoursUseCase``'s module docstring for the one
knock-on limitation this leaves: overlap is still only checked within
a single ``day_of_week``, not across the midnight boundary into the
next day's own rows.
"""

from __future__ import annotations

from datetime import time

from pydantic import Field, model_validator

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.restaurant.domain.entities import day_of_week_name


class OperatingHoursEntryRequestSchema(CamelModel):
    day_of_week: int = Field(..., ge=0, le=6)
    is_closed: bool = False
    opens_at: time | None = None
    closes_at: time | None = None

    @model_validator(mode="after")
    def _check_open_entry_has_valid_times(self) -> OperatingHoursEntryRequestSchema:
        if not self.is_closed:
            day_name = day_of_week_name(self.day_of_week)
            if self.opens_at is None or self.closes_at is None:
                raise ValueError(f"{day_name}: an open entry requires both opensAt and closesAt")
            if self.opens_at == self.closes_at:
                raise ValueError(f"{day_name}: opening and closing time cannot be the same")
        return self


class ReplaceOperatingHoursRequestSchema(CamelModel):
    entries: list[OperatingHoursEntryRequestSchema] = Field(default_factory=list)


class OperatingHoursEntryResponseSchema(CamelModel):
    id: str
    day_of_week: int
    is_closed: bool
    opens_at: time | None
    closes_at: time | None
