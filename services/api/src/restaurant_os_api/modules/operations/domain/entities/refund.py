"""Refund entity.

**Retired from the active product surface (P0 correction,
2026-08-12).** RestaurantOS v1 does not provide a customer refund
workflow -- a failed/reversed/disputed transaction is handled entirely
through the relevant payment provider/bank, outside RestaurantOS. This
entity, ``RequestRefundUseCase``, its repository methods, and the
reversing ledger logic are all still present and unit-tested,
preserving the abstraction for a possible future real payment-gateway
integration, but no REST route constructs one anymore (see
``payment_router.py``'s own docstring).

``approved_by_user_id`` is required at construction (unlike
``BillAdjustment``'s optional one) -- Architecture doc SS3.4: every
refund needs a named approver. No separate async approval queue exists
in this step (disclosed in ``request_refund.py``): a refund is
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
