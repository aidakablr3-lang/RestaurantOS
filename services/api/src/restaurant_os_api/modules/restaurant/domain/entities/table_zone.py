"""TableZone entity.

Restaurant Platform Architecture SS3.1: a named grouping of tables for
floor-plan organization (Data Architecture v1.0 SS3.2, unchanged name
and shape -- not renamed "DiningArea").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TableZone:
    id: str
    tenant_id: str
    branch_id: str
    name: str
    display_order: int
    created_at: datetime
