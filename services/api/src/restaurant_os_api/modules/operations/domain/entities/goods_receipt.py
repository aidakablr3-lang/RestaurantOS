"""GoodsReceipt -- confirming one is what actually writes the
``StockMovement(movement_type='receipt')`` rows (Architecture doc
SS3.7); the PO/receipt paperwork and the stock-level truth are
deliberately two different writes, never conflated. Driven
synchronously in one call by ``ConfirmGoodsReceiptUseCase`` (created,
then immediately confirmed) -- the same "no separate async workflow in
this scope" precedent ``Payment``/``Refund`` already established in
Step 4, disclosed rather than silently building a real receiving
workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidGoodsReceiptStatusTransitionError,
)


class GoodsReceiptStatus(StrEnum):
    CREATED = "created"
    CONFIRMED = "confirmed"


@dataclass(slots=True)
class GoodsReceipt:
    id: str
    tenant_id: str
    purchase_order_id: str
    status: GoodsReceiptStatus
    received_at: datetime
    created_at: datetime
    has_discrepancy: bool = False

    def confirm(self) -> None:
        if self.status != GoodsReceiptStatus.CREATED:
            raise InvalidGoodsReceiptStatusTransitionError(
                self.id, self.status.value, GoodsReceiptStatus.CONFIRMED.value
            )
        self.status = GoodsReceiptStatus.CONFIRMED
