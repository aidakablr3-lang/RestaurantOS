"""KitchenTicket entity -- aggregate root over its own ``KitchenItem``
children. ``station`` is an attribute, not a separate entity
(Architecture doc SS3.2, matching the source catalogue's own explicit
scope note). One Order can fan out into multiple tickets (one per
station); each ticket ages independently.

This step's KitchenTicket status is settable directly via its own
route, independent of its items' individual statuses -- no invariant
enforcing "ticket can only be marked ready once every item is ready"
is implemented yet (that stricter cross-child rule is real, disclosed
future work, not silently assumed).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidKitchenTicketStatusTransitionError,
)


class KitchenTicketStatus(StrEnum):
    FIRED = "fired"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    SERVED = "served"


@dataclass(slots=True)
class KitchenTicket:
    id: str
    tenant_id: str
    order_id: str
    station: str
    status: KitchenTicketStatus
    created_at: datetime

    def start(self) -> None:
        self._transition_to(
            KitchenTicketStatus.IN_PROGRESS, allowed_from=(KitchenTicketStatus.FIRED,)
        )

    def mark_ready(self) -> None:
        self._transition_to(
            KitchenTicketStatus.READY, allowed_from=(KitchenTicketStatus.IN_PROGRESS,)
        )

    def mark_served(self) -> None:
        self._transition_to(KitchenTicketStatus.SERVED, allowed_from=(KitchenTicketStatus.READY,))

    def _transition_to(
        self, new_status: KitchenTicketStatus, *, allowed_from: tuple[KitchenTicketStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidKitchenTicketStatusTransitionError(
                self.id, self.status.value, new_status.value
            )
        self.status = new_status
