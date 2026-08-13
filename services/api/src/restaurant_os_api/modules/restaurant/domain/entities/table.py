"""Table entity.

Restaurant Platform Architecture SS3.1: a physical seating unit.
``status`` is the Conflict Resolution Registry's own worked example of
"Exclusive shared state" (SS9.4/SS10) -- server-authoritative,
first-commit-receipt order, hence ``sync_version`` even though nothing
writes it via sync yet this sprint. "Retired" (the slower floor-plan
lifecycle distinct from the high-frequency ``status`` field) is
represented by the existing soft-delete mechanism, not a second status
column -- the architecture document's own representative DDL (SS9.3)
shows only one status column on this table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TableStatus(StrEnum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    CLEANING = "cleaning"


@dataclass(slots=True)
class Table:
    id: str
    tenant_id: str
    branch_id: str
    table_zone_id: str
    table_number: str
    capacity: int
    status: TableStatus
    sync_version: int
    created_at: datetime
