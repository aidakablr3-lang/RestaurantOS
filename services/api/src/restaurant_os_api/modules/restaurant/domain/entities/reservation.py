"""Reservation entity (foundation only).

Restaurant Platform Architecture SS3.1: a booked table request or
walk-in waitlist entry, built to foundation depth only -- no
waitlist-time-estimation, no automated table-assignment optimization
(Blueprint Phase 2+ concerns). ``table_id`` assignment is the Conflict
Resolution Registry's "Exclusive shared state" category (SS10),
alongside ``Table.status`` -- hence ``sync_version``.

The six states (``requested``, ``confirmed``, ``seated``, ``completed``,
``no_show``, ``canceled``) are catalogue-specified; the transition graph
below is a reasonable, standard restaurant-reservation interpretation
this document derives from the state names themselves, disclosed as a
judgment call rather than an architecture-mandated rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.restaurant.domain.exceptions import (
    InvalidReservationStatusTransitionError,
)


class ReservationStatus(StrEnum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELED = "canceled"


@dataclass(slots=True)
class Reservation:
    id: str
    tenant_id: str
    branch_id: str
    party_size: int
    requested_at: datetime
    status: ReservationStatus
    sync_version: int
    created_at: datetime
    table_id: str | None = None
    customer_id: str | None = None

    def confirm(self) -> None:
        self._transition_to(
            ReservationStatus.CONFIRMED, allowed_from=(ReservationStatus.REQUESTED,)
        )

    def seat(self) -> None:
        self._transition_to(ReservationStatus.SEATED, allowed_from=(ReservationStatus.CONFIRMED,))

    def complete(self) -> None:
        self._transition_to(ReservationStatus.COMPLETED, allowed_from=(ReservationStatus.SEATED,))

    def mark_no_show(self) -> None:
        self._transition_to(ReservationStatus.NO_SHOW, allowed_from=(ReservationStatus.CONFIRMED,))

    def cancel(self) -> None:
        self._transition_to(
            ReservationStatus.CANCELED,
            allowed_from=(ReservationStatus.REQUESTED, ReservationStatus.CONFIRMED),
        )

    def _transition_to(
        self, new_status: ReservationStatus, *, allowed_from: tuple[ReservationStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidReservationStatusTransitionError(
                self.id, self.status.value, new_status.value
            )
        self.status = new_status
