"""MenuItemAvailability entity.

Restaurant Platform Architecture SS3.1: the availability-dimension twin
of ``MenuItemBranchPrice`` -- a branch- and time-scoped override of
``menu_items.is_available``. ``effective_to = None`` is an open-ended
86 until manually cleared (the Blueprint's "86 List Management" screen).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MenuItemAvailability:
    id: str
    tenant_id: str
    branch_id: str
    menu_item_id: str
    is_available: bool
    effective_from: datetime
    created_at: datetime
    effective_to: datetime | None = None
