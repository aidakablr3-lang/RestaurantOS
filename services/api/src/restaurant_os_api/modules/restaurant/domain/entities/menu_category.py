"""MenuCategory entity.

Restaurant Platform Architecture SS3.1: a named grouping of sellable
items, belonging to ``Restaurant`` -- deliberately **not** ``Branch``
(SS3, SS5): branch-specific menu behavior is handled by
``MenuItemBranchPrice``/``MenuItemAvailability`` override rows, not by
scoping the category itself to a branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MenuCategory:
    id: str
    tenant_id: str
    restaurant_id: str
    name: str
    display_order: int
    created_at: datetime
