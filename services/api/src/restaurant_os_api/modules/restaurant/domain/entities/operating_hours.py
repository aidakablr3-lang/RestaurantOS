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
