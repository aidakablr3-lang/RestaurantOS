"""Shared OperatingHours (domain entity) -> OperatingHoursEntryDTO mapping.

Private to this package, matching ``_branch_mapper.py``'s convention.
"""

from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import OperatingHoursEntryDTO
from restaurant_os_api.modules.restaurant.domain.entities import OperatingHours


def operating_hours_to_dto(entry: OperatingHours) -> OperatingHoursEntryDTO:
    return OperatingHoursEntryDTO(
        id=entry.id,
        day_of_week=entry.day_of_week,
        is_closed=entry.is_closed,
        opens_at=entry.opens_at,
        closes_at=entry.closes_at,
    )
