from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import ReservationDTO
from restaurant_os_api.modules.restaurant.domain.entities import Reservation


def reservation_to_dto(reservation: Reservation) -> ReservationDTO:
    return ReservationDTO(
        id=reservation.id,
        tenant_id=reservation.tenant_id,
        branch_id=reservation.branch_id,
        table_id=reservation.table_id,
        customer_id=reservation.customer_id,
        party_size=reservation.party_size,
        requested_at=reservation.requested_at,
        status=reservation.status.value,
        created_at=reservation.created_at,
    )
