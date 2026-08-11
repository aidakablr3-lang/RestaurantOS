"""PurchaseOrderItem -- a line on a PurchaseOrder (Architecture doc
SS3.7). ``quantity_received`` is a running total, incremented by
``receive()`` once per matching ``GoodsReceipt`` line -- never capped
at ``quantity_ordered`` here: over-receiving is allowed (flagged as a
discrepancy at the ``GoodsReceipt`` level, not rejected as an error),
matching the architecture doc's own "discrepancy flag(s)" field on
``GoodsReceipt`` rather than a hard constraint on this entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class PurchaseOrderItem:
    id: str
    tenant_id: str
    purchase_order_id: str
    inventory_item_id: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    created_at: datetime

    def receive(self, quantity: Decimal) -> None:
        self.quantity_received += quantity
