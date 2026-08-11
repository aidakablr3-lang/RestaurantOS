"""PurchaseOrder entity -- Architecture doc SS3.7's ``draft -> sent ->
(partially) received -> fully received`` graph, plus ``draft``/``sent
-> canceled``. The receipt-driven transitions (``partially_received``/
``fully_received``) are never chosen by a caller directly -- they are
computed by ``ConfirmGoodsReceiptUseCase`` from the actual line-item
totals after a receipt posts, via ``apply_receipt_status()``, the same
"use case computes, entity just records" shape ``Bill.apply_payment_status()``
already established in Step 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidPurchaseOrderStatusTransitionError,
)


class PurchaseOrderStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    PARTIALLY_RECEIVED = "partially_received"
    FULLY_RECEIVED = "fully_received"
    CANCELED = "canceled"


@dataclass(slots=True)
class PurchaseOrder:
    id: str
    tenant_id: str
    branch_id: str
    supplier_id: str
    status: PurchaseOrderStatus
    created_at: datetime

    def send(self) -> None:
        self._transition_to(PurchaseOrderStatus.SENT, allowed_from=(PurchaseOrderStatus.DRAFT,))

    def cancel(self) -> None:
        self._transition_to(
            PurchaseOrderStatus.CANCELED,
            allowed_from=(PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.SENT),
        )

    def ensure_receivable(self) -> None:
        """Raised proactively by ``ConfirmGoodsReceiptUseCase`` before
        it does any work -- a receipt can only land against a PO that
        has actually been sent and isn't already fully received or
        canceled."""
        if self.status not in (
            PurchaseOrderStatus.SENT,
            PurchaseOrderStatus.PARTIALLY_RECEIVED,
        ):
            raise InvalidPurchaseOrderStatusTransitionError(
                self.id, self.status.value, PurchaseOrderStatus.PARTIALLY_RECEIVED.value
            )

    def apply_receipt_status(self, *, fully_received: bool) -> None:
        self.status = (
            PurchaseOrderStatus.FULLY_RECEIVED
            if fully_received
            else PurchaseOrderStatus.PARTIALLY_RECEIVED
        )

    def _transition_to(
        self, new_status: PurchaseOrderStatus, *, allowed_from: tuple[PurchaseOrderStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidPurchaseOrderStatusTransitionError(
                self.id, self.status.value, new_status.value
            )
        self.status = new_status
