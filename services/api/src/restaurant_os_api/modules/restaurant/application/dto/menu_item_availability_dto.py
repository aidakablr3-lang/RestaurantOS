"""Application-layer DTOs for MenuItemAvailability (Sprint 5 Step 4.10).

No update/delete DTOs -- ``MenuItemAvailabilityRepository`` only
exposes ``create``/``list_for_menu_item``, the same append-only-history
shape as ``MenuItemBranchPrice``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateMenuItemAvailabilityRequestDTO:
    menu_item_id: str
    branch_id: str
    is_available: bool
    effective_from: datetime
    effective_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class MenuItemAvailabilityDTO:
    id: str
    tenant_id: str
    branch_id: str
    menu_item_id: str
    is_available: bool
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
