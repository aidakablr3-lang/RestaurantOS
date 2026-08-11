"""Refund entity -- the only mechanism for correcting a closed
Order/Bill/Payment. ``approved_by_user_id`` is required at construction
(unlike ``BillAdjustment``'s optional one) -- Architecture doc SS3.4:
every refund needs a named approver. No separate async approval queue
exists in this step (disclosed in ``request_refund.py``): a refund is
requested, approved, and processed synchronously in one call, so
``approve()``/``process()`` are both invoked by that one use case
rather than by two separate future routes -- kept as distinct methods,
not collapsed, so a later async approval workflow can call them
independently without an entity change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidRefundStatusTransitionError,
)


class RefundStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSED = "processed"


@dataclass(slots=True)
class Refund:
    id: str
    tenant_id: str
    branch_id: str
    payment_id: str
    order_id: str
    approved_by_user_id: str
    amount: Decimal
    status: RefundStatus
    created_at: datetime

    def approve(self) -> None:
        self._transition_to(RefundStatus.APPROVED, allowed_from=(RefundStatus.REQUESTED,))

    def process(self) -> None:
        self._transition_to(RefundStatus.PROCESSED, allowed_from=(RefundStatus.APPROVED,))

    def _transition_to(
        self, new_status: RefundStatus, *, allowed_from: tuple[RefundStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidRefundStatusTransitionError(self.id, self.status.value, new_status.value)
        self.status = new_status
