"""MenuItemBranchPrice entity.

Already fully specified by Data Architecture v2.0 Group J -- not
redesigned here, only implemented. When a row exists for
``(menu_item, branch, now())``, it overrides ``menu_items.price_amount``;
absent, the global default applies. The *only* mechanism Restaurant
Platform needs for branch-specific pricing and scheduled pricing
windows (breakfast/lunch/dinner, and future happy-hour pricing --
Restaurant Platform Architecture SS5/SS6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class MenuItemBranchPrice:
    id: str
    tenant_id: str
    branch_id: str
    menu_item_id: str
    price_amount: Decimal
    effective_from: datetime
    created_at: datetime
    effective_to: datetime | None = None
