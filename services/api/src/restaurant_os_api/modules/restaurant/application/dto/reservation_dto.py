"""Application-layer DTOs for Reservation CRUD (Sprint 5 Step 4.11).

``customer_id`` is deliberately absent from every request DTO here --
the ``Customer`` entity/table doesn't exist anywhere in this codebase
yet (Architecture SS3.1's own note: "declared but... unpopulated until
the CRM Platform exists," the same reserved-but-inert shape as
``MenuItem.recipe_id``). A client-supplied ``customer_id`` with no
table to validate it against would be an unchecked foreign reference,
not a real relationship -- every reservation created through this
step is necessarily a guest/walk-in reservation with
``customer_id = None``.

``status`` is present on ``UpdateReservationRequestDTO`` (unlike
``UpdateTableRequestDTO``, which excludes it) because Reservation has
no separate flat status-change route the way Table does (Architecture
SS7 specifies only ``POST``/``GET``/``PATCH`` for Reservation, no
fourth route) -- the single ``PATCH`` handles both plain field edits
and status transitions. ``party_size`` and ``status`` are both
optional: omitting ``status`` means "no transition requested, only
other fields are applied"; omitting ``party_size`` means "leave it
unchanged." A caller can therefore PATCH just a status transition, or
just a field edit, without resending the other. A non-``None`` target
status is routed through the matching domain transition method (see
``update_reservation.py``), never assigned directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateReservationRequestDTO:
    branch_id: str
    party_size: int
    requested_at: datetime
    table_id: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateReservationRequestDTO:
    reservation_id: str
    branch_id: str
    party_size: int | None = None
    status: str | None = None
    table_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReservationDTO:
    id: str
    tenant_id: str
    branch_id: str
    party_size: int
    requested_at: datetime
    status: str
    created_at: datetime
    table_id: str | None
    customer_id: str | None


@dataclass(frozen=True, slots=True)
class ReservationListResultDTO:
    reservations: list[ReservationDTO]
    total: int
    offset: int
    limit: int
