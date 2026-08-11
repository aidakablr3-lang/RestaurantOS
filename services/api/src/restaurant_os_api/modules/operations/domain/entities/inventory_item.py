"""InventoryItem -- a branch-scoped ingredient/stock line (Architecture
doc SS3.6). ``quantity_on_hand`` is **derived/cached**, maintained
exclusively by the ``enforce_stock_movement_and_update_balance()``
database trigger on every ``stock_movements`` insert -- application
code only ever reads it here (via a fresh repository load after a
movement is written), never assigns it directly. The same branch-scoped
shape ``MenuItemBranchPrice`` already established: the same ingredient
at two branches is two separate rows, not one row with a branch
override table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class InventoryItem:
    id: str
    tenant_id: str
    branch_id: str
    inventory_category_id: str
    name: str
    unit: str
    quantity_on_hand: Decimal
    created_at: datetime
    reorder_point: Decimal | None = None
    allow_negative_stock_override: bool | None = None
