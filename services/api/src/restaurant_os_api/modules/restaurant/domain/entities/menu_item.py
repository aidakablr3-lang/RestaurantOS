"""MenuItem entity.

Restaurant Platform Architecture SS3.1: a sellable product, the unit
priced, ordered, and (future) recipe-costed. Restaurant-scoped like
``MenuCategory``, not branch-scoped -- the branch dimension lives
entirely on the override tables (``MenuItemBranchPrice``/
``MenuItemAvailability``). ``recipe_id`` is a reserved, nullable FK
target for the future Inventory Platform -- unpopulated this sprint,
since ``Recipe`` doesn't exist yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class MenuItem:
    id: str
    tenant_id: str
    menu_category_id: str
    name: str
    price_amount: Decimal
    currency_code: str
    is_available: bool
    display_order: int
    created_at: datetime
    recipe_id: str | None = None
