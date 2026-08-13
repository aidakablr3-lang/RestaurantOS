"""ListTableZonesUseCase -- branch-scoped, offset/limit paginated,
deterministic ordering by ``display_order``
(``TableZoneRepository.list_for_branch`` -- the "reorder" action
SS8's Dining Areas screen names is exactly re-saving each row's
``display_order`` via ``PATCH``, read back here in that same order).

``branch_id`` is verified to exist (scoped to the caller's tenant)
before listing, mirroring ``CreateTableZoneUseCase``'s own check --
an unknown or cross-tenant branch is ``BranchNotFoundError``, not an
empty list.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import TableZoneListResultDTO
from restaurant_os_api.modules.restaurant.application.use_cases._table_zone_mapper import (
    table_zone_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, TableZoneRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListTableZonesUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        table_zone_repository_factory: Callable[[AsyncSession], TableZoneRepository],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._table_zone_repository_factory = table_zone_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> TableZoneListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            table_zone_repo = self._table_zone_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, branch_id)
            if branch is None:
                raise BranchNotFoundError(branch_id)

            table_zones, total = await table_zone_repo.list_for_branch(
                tenant_id, branch_id, offset=offset, limit=limit
            )

        return TableZoneListResultDTO(
            table_zones=[table_zone_to_dto(tz) for tz in table_zones],
            total=total,
            offset=offset,
            limit=limit,
        )
