"""Application-layer DTOs for MenuItemBranchPrice (Sprint 5 Step 4.10).

No update/delete DTOs -- ``MenuItemBranchPriceRepository`` only
exposes ``create``/``list_for_menu_item``; a new override row
supersedes an old one by effective-window ordering, matching how the
architecture's own "multiple historical override windows are
legitimate" framing treats this as an append-only history, not an
editable resource.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreateMenuItemBranchPriceRequestDTO:
    menu_item_id: str
    branch_id: str
    price_amount: Decimal
    effective_from: datetime
    effective_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class MenuItemBranchPriceDTO:
    id: str
    tenant_id: str
    branch_id: str
    menu_item_id: str
    price_amount: Decimal
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
