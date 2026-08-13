"""Tab entity -- lets several Orders (a merged-table party, a running
bar tab) close out under one Bill later (Data Architecture v2.0 Group
E). Simple open/closed lifecycle; Bill's own ``order_id``/``tab_id``
XOR relationship is a Step 4 (Billing) concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidTabStatusTransitionError,
)


class TabStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(slots=True)
class Tab:
    id: str
    tenant_id: str
    branch_id: str
    status: TabStatus
    opened_at: datetime
    created_at: datetime
    table_id: str | None = None
    customer_id: str | None = None
    closed_at: datetime | None = None

    def close(self, *, closed_at: datetime) -> None:
        if self.status != TabStatus.OPEN:
            raise InvalidTabStatusTransitionError(
                self.id, self.status.value, TabStatus.CLOSED.value
            )
        self.status = TabStatus.CLOSED
        self.closed_at = closed_at
