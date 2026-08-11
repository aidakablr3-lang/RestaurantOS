"""StockAdjustment -- the human-readable "why" behind a manual stock
correction (Architecture doc SS3.6). ``approved_by_user_id`` is
``NOT NULL`` at the schema level, so unlike ``Payment``/``Refund``'s
own multi-state machines, there is no separate "recorded, not yet
approved" persisted state here -- ``RecordStockMovementUseCase`` creates
the linked ``StockMovement`` and this row together, in the same
transaction, only for ``movement_type='adjustment'`` (never mutates
stock directly itself, per the architecture doc -- the actual quantity
change is always the linked ``StockMovement`` row)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class StockAdjustment:
    id: str
    tenant_id: str
    branch_id: str
    inventory_item_id: str
    reason: str
    approved_by_user_id: str
    created_at: datetime
    stock_movement_id: str | None = None
