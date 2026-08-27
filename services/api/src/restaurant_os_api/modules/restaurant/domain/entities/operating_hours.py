"""OperatingHours entity.

Restaurant Platform Architecture SS3.1: a branch's weekly service-hours
schedule. Reference/config data, not a versioned/historical entity. At
most 7 rows per branch is the common case, but the natural key is not
simply ``(branch_id, day_of_week)`` -- a branch with split shifts
(lunch + dinner) needs two rows for the same day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time


@dataclass(slots=True)
class OperatingHours:
    id: str
    tenant_id: str
    branch_id: str
    day_of_week: int
    is_closed: bool
    created_at: datetime
    opens_at: time | None = None
    closes_at: time | None = None


_DAY_NAMES: tuple[str, ...] = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)


def day_of_week_name(day_of_week: int) -> str:
    """0=Sunday..6=Saturday -- matches admin-web's own ``dayLabel()``
    (apps/admin-web/src/lib/schemas/branch.ts). Keep both lists in sync
    if either changes."""
    if 0 <= day_of_week <= 6:
        return _DAY_NAMES[day_of_week]
    return f"day {day_of_week}"
