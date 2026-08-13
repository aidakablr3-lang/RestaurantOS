"""Application-layer DTOs for Operating Hours.

Architecture SS7: a single full-week replace (``PUT /branches/{id}/
operating-hours``), not per-entry CRUD -- ``ReplaceOperatingHoursRequestDTO``
carries the *entire* submitted week as one list, matching
``OperatingHoursRepository.replace_for_branch``'s own shape (Step 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True, slots=True)
class OperatingHoursEntryRequestDTO:
    day_of_week: int
    is_closed: bool
    opens_at: time | None = None
    closes_at: time | None = None


@dataclass(frozen=True, slots=True)
class ReplaceOperatingHoursRequestDTO:
    branch_id: str
    entries: list[OperatingHoursEntryRequestDTO]


@dataclass(frozen=True, slots=True)
class OperatingHoursEntryDTO:
    id: str
    day_of_week: int
    is_closed: bool
    opens_at: time | None
    closes_at: time | None
