"""GetReservationUseCase.

Restaurant Platform Architecture SS7's ``GET /api/v1/branches/
{branch_id}/reservations/{id}``. Same cross-branch scoping discipline
as ``GetTableUseCase`` -- a reservation that exists but belongs to a
*different* branch than the URL's own is ``ReservationNotFoundError``,
not a distinguishable error.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import ReservationDTO
from restaurant_os_api.modules.restaurant.application.use_cases._reservation_mapper import (
    reservation_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import ReservationNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import ReservationRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetReservationUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        reservation_repository_factory: Callable[[AsyncSession], ReservationRepository],
    ) -> None:
        self._session_factory = session_factory
        self._reservation_repository_factory = reservation_repository_factory

    async def execute(self, tenant_id: str, branch_id: str, reservation_id: str) -> ReservationDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            reservation_repo = self._reservation_repository_factory(uow.session)
            reservation = await reservation_repo.get_by_id(tenant_id, reservation_id)

        if reservation is None or reservation.branch_id != branch_id:
            raise ReservationNotFoundError(reservation_id)

        return reservation_to_dto(reservation)
