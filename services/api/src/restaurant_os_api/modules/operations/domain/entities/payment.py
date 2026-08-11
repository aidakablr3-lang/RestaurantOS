"""Payment entity. ``gateway_token_ref``/``gateway_last4`` are
passthrough references only -- no real gateway integration exists
(Architecture doc SS2.1's own disclosed scope cut), so
``RecordPaymentUseCase`` drives a payment straight through
``authorized -> captured -> settled`` synchronously in one call rather
than waiting on an async gateway callback. The three-state machine is
kept (not collapsed to a single "paid" flag) so a future real gateway
integration slots in without a schema/entity change -- only the use
case's own synchronous chaining would need to become async.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidPaymentStatusTransitionError,
)


class TenderType(StrEnum):
    CASH = "cash"
    CARD = "card"
    WALLET = "wallet"


class PaymentStatus(StrEnum):
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    SETTLED = "settled"
    DECLINED = "declined"


@dataclass(slots=True)
class Payment:
    id: str
    tenant_id: str
    branch_id: str
    bill_id: str
    tender_type: TenderType
    amount: Decimal
    currency_code: str
    tip_amount: Decimal
    status: PaymentStatus
    created_at: datetime
    gateway_token_ref: str | None = None
    gateway_last4: str | None = None

    def capture(self) -> None:
        self._transition_to(PaymentStatus.CAPTURED, allowed_from=(PaymentStatus.AUTHORIZED,))

    def settle(self) -> None:
        self._transition_to(PaymentStatus.SETTLED, allowed_from=(PaymentStatus.CAPTURED,))

    def decline(self) -> None:
        self._transition_to(PaymentStatus.DECLINED, allowed_from=(PaymentStatus.AUTHORIZED,))

    def _transition_to(
        self, new_status: PaymentStatus, *, allowed_from: tuple[PaymentStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidPaymentStatusTransitionError(self.id, self.status.value, new_status.value)
        self.status = new_status
