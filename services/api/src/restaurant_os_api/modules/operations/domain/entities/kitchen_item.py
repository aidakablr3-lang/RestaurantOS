"""KitchenItem entity -- one line within a KitchenTicket, lets a ticket
be partially ready (some items done, others still cooking) at the
granularity the KDS's own "bump" action operates on. Child of the
KitchenTicket aggregate, never persisted independently.

``cancel()`` (operational-gap fix, 2026-09-08): cascaded down from
``KitchenTicket.cancel()`` -- see that entity's own docstring. Allowed
from any pre-served status (``KitchenItemStatus`` has no ``served``
value of its own -- see the module docstring above, it "stops at
ready"), so every non-terminal item status is cancellable.
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
    CANCELLED = "cancelled"


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

    def cancel(self) -> None:
        self._transition_to(
            KitchenItemStatus.CANCELLED,
            allowed_from=(
                KitchenItemStatus.QUEUED,
                KitchenItemStatus.IN_PROGRESS,
                KitchenItemStatus.READY,
            ),
        )

    def _transition_to(
        self, new_status: KitchenItemStatus, *, allowed_from: tuple[KitchenItemStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidKitchenItemStatusTransitionError(
                self.id, self.status.value, new_status.value
            )
        self.status = new_status
