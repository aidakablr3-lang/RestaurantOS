"""KitchenItem entity -- one line within a KitchenTicket, lets a ticket
be partially ready (some items done, others still cooking) at the
granularity the KDS's own "bump" action operates on. Child of the
KitchenTicket aggregate, never persisted independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidKitchenItemStatusTransitionError,
)


class KitchenItemStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    READY = "ready"


@dataclass(slots=True)
class KitchenItem:
    id: str
    tenant_id: str
    kitchen_ticket_id: str
    order_item_id: str
    status: KitchenItemStatus
    created_at: datetime

    def start(self) -> None:
        self._transition_to(KitchenItemStatus.IN_PROGRESS, allowed_from=(KitchenItemStatus.QUEUED,))

    def mark_ready(self) -> None:
        self._transition_to(KitchenItemStatus.READY, allowed_from=(KitchenItemStatus.IN_PROGRESS,))

    def _transition_to(
        self, new_status: KitchenItemStatus, *, allowed_from: tuple[KitchenItemStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidKitchenItemStatusTransitionError(
                self.id, self.status.value, new_status.value
            )
        self.status = new_status
