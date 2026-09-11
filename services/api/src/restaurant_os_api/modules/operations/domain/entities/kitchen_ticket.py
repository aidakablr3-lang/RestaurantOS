"""KitchenTicket entity -- aggregate root over its own ``KitchenItem``
children. ``station`` is an attribute, not a separate entity
(Architecture doc SS3.2, matching the source catalogue's own explicit
scope note). One Order can fan out into multiple tickets (one per
station); each ticket ages independently.

This step's KitchenTicket status is settable directly via its own
route. ``UpdateKitchenTicketStatusUseCase`` cascades a ``start()``/
``mark_ready()`` transition down to any child ``KitchenItem`` still
behind it, so bumping the whole ticket also bumps items nobody bumped
individually -- but an item can still be bumped ahead of its ticket
through its own route (a cook marking one item ready before the rest),
and no invariant enforces "ticket can only be marked ready once every
item is ready" (that stricter cross-child rule is real, disclosed
future work, not silently assumed).

``cancel()`` (operational-gap fix, 2026-09-08): the KDS-visible
counterpart to ``VoidOrderUseCase`` voiding the parent ``Order`` --
previously a post-fire void left the ticket sitting on the board in
whatever status it was in, with nothing telling the kitchen to stop.
Allowed from ``fired``/``in_progress``/``ready`` (a chef could be
mid-dish at any of those) but not from ``served`` -- a served ticket
already reached the guest, cancelling it after the fact would be a
lie, not a correction. ``cancelled_at`` is stamped by the caller (same
shape as ``Order.closed_at``), not defaulted here, so the KDS can
compute "how long has this been cancelled" without this entity needing
clock access of its own.
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
    CANCELLED = "cancelled"


@dataclass(slots=True)
class KitchenTicket:
    id: str
    tenant_id: str
    order_id: str
    station: str
    status: KitchenTicketStatus
    created_at: datetime
    cancelled_at: datetime | None = None

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

    def cancel(self, *, cancelled_at: datetime) -> None:
        self._transition_to(
            KitchenTicketStatus.CANCELLED,
            allowed_from=(
                KitchenTicketStatus.FIRED,
                KitchenTicketStatus.IN_PROGRESS,
                KitchenTicketStatus.READY,
            ),
        )
        self.cancelled_at = cancelled_at

    def _transition_to(
        self, new_status: KitchenTicketStatus, *, allowed_from: tuple[KitchenTicketStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidKitchenTicketStatusTransitionError(
                self.id, self.status.value, new_status.value
            )
        self.status = new_status
