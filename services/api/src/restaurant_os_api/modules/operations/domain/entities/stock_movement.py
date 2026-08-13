"""StockMovement -- the append-only inventory ledger (Architecture doc
SS3.6, Data Architecture v2.0 Group D). Written once, never edited;
``InventoryItem.quantity_on_hand`` is derived from summing this table
via a DB trigger, the same "ledger is truth, balance is cache" shape
``sync_version`` uses for optimistic concurrency elsewhere.

``sale_deduction`` (automatic deduction on order-item service) is not
written by anything in this step -- it requires ``OrderItem``'s own
``served`` transition and KDS-bump-to-order-item propagation, neither
of which exist yet (disclosed in ``order_item.py``'s own docstring as
future work, not a Step 5 gap). This step's ``RecordStockMovementUseCase``
writes ``adjustment``/``waste``/``transfer`` rows only, driven by a
direct manual API call; ``receipt`` is Step 6 (Purchasing)'s own
``GoodsReceipt``-confirmation concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class StockMovementType(StrEnum):
    SALE_DEDUCTION = "sale_deduction"
    ADJUSTMENT = "adjustment"
    RECEIPT = "receipt"
    WASTE = "waste"
    TRANSFER = "transfer"


@dataclass(slots=True)
class StockMovement:
    id: str
    tenant_id: str
    branch_id: str
    inventory_item_id: str
    movement_type: StockMovementType
    quantity_delta: Decimal
    occurred_at: datetime
    created_at: datetime
    reference_type: str | None = None
    reference_id: str | None = None
    idempotency_key: str | None = None
