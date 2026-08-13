"""ModifierGroup entity.

Restaurant Platform Architecture SS3.1: a named set of choices for a
menu item, shareable across multiple items (Data Architecture v2.0
Group F). Name uniqueness is deliberately **not** enforced -- a group
named "Size" legitimately repeats across unrelated item families.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ModifierSelectionType(StrEnum):
    SINGLE = "single"
    MULTIPLE = "multiple"


@dataclass(slots=True)
class ModifierGroup:
    id: str
    tenant_id: str
    name: str
    selection_type: ModifierSelectionType
    created_at: datetime
