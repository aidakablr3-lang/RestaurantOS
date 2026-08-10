"""ListReservationsUseCase -- branch-scoped, offset/limit paginated,
mirroring ``ListTablesUseCase``'s own shape exactly. ``branch_id`` is
verified to exist (scoped to the caller's tenant) before listing.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import ReservationListResultDTO
from restaurant_os_api.modules.restaurant.application.use_cases._reservation_mapper import (
    reservation_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    ReservationRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListReservationsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        reservation_repository_factory: Callable[[AsyncSession], ReservationRepository],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._reservation_repository_factory = reservation_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> ReservationListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            reservation_repo = self._reservation_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, branch_id)
            if branch is None:
                raise BranchNotFoundError(branch_id)

            reservations, total = await reservation_repo.list_for_branch(
                tenant_id, branch_id, offset=offset, limit=limit
            )

        return ReservationListResultDTO(
            reservations=[reservation_to_dto(r) for r in reservations],
            total=total,
            offset=offset,
            limit=limit,
        )
