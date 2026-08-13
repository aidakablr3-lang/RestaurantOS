"""Repository port for Reservation."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import Reservation


class ReservationRepository(Protocol):
    async def get_by_id(self, tenant_id: str, reservation_id: str) -> Reservation | None: ...

    async def create(self, reservation: Reservation) -> Reservation: ...

    async def update(self, reservation: Reservation) -> Reservation: ...

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[Reservation], int]: ...
