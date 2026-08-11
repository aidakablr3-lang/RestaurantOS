"""CashDrawer entity. The Blueprint's "daily cash-up automatically
reconciled against POS sales" story reads a closed drawer against the
sum of its shift's cash Payments -- a query the use case layer performs
(``CloseCashDrawerUseCase``), not a separate reconciliation entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidCashDrawerStatusTransitionError,
)


class CashDrawerStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(slots=True)
class CashDrawer:
    id: str
    tenant_id: str
    branch_id: str
    status: CashDrawerStatus
    opening_float_amount: Decimal
    opened_at: datetime
    created_at: datetime
    terminal_id: str | None = None
    closing_counted_amount: Decimal | None = None
    closed_at: datetime | None = None

    def close(self, *, closing_counted_amount: Decimal, closed_at: datetime) -> None:
        if self.status != CashDrawerStatus.OPEN:
            raise InvalidCashDrawerStatusTransitionError(
                self.id, self.status.value, CashDrawerStatus.CLOSED.value
            )
        self.status = CashDrawerStatus.CLOSED
        self.closing_counted_amount = closing_counted_amount
        self.closed_at = closed_at
