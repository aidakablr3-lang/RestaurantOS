"""Pydantic request/response schemas for Reservation CRUD (Sprint 5
Step 4.11).

``customerId`` is deliberately absent from every schema here -- see
``application/dto/reservation_dto.py``'s own docstring for why (no
``Customer`` entity/table exists anywhere in this codebase yet).

``status`` is present on ``UpdateReservationRequestSchema`` -- unlike
``UpdateTableRequestSchema``, Reservation has no separate flat
status-change route, so the one ``PATCH`` carries the caller's
intended status alongside the plain editable fields. See
``update_reservation.py`` for how a target equal to the current status
is treated as "no transition requested."
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.restaurant.domain.entities import ReservationStatus


class CreateReservationRequestSchema(CamelModel):
    party_size: int = Field(..., gt=0)
    requested_at: datetime
    table_id: str | None = Field(default=None, min_length=26, max_length=26)


class UpdateReservationRequestSchema(CamelModel):
    party_size: int = Field(..., gt=0)
    status: ReservationStatus
    table_id: str | None = Field(default=None, min_length=26, max_length=26)


class ReservationResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    party_size: int
    requested_at: datetime
    status: str
    created_at: datetime
    table_id: str | None
    customer_id: str | None
