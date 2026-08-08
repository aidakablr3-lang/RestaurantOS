"""GetTableZoneUseCase.

Restaurant Platform Architecture SS7's ``GET /api/v1/branches/
{branch_id}/table-zones/{id}``. The route is nested under a specific
branch (so ``require_branch_permission`` can gate on the URL's own
``branch_id``, reusing the existing branch-authorization mechanism
rather than inventing a new one for a flat ``/table-zones/{id}``
route) -- so a table zone that exists but belongs to a *different*
branch than the URL's own must be treated identically to one that
does not exist at all, the same "belt and suspenders" scoping
discipline used everywhere else for cross-tenant access, applied here
one level down for cross-*branch* access within the same tenant.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import TableZoneDTO
from restaurant_os_api.modules.restaurant.application.use_cases._table_zone_mapper import (
    table_zone_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import TableZoneNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import TableZoneRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetTableZoneUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        table_zone_repository_factory: Callable[[AsyncSession], TableZoneRepository],
    ) -> None:
        self._session_factory = session_factory
        self._table_zone_repository_factory = table_zone_repository_factory

    async def execute(self, tenant_id: str, branch_id: str, table_zone_id: str) -> TableZoneDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            table_zone_repo = self._table_zone_repository_factory(uow.session)
            table_zone = await table_zone_repo.get_by_id(tenant_id, table_zone_id)

        if table_zone is None or table_zone.branch_id != branch_id:
            raise TableZoneNotFoundError(table_zone_id)

        return table_zone_to_dto(table_zone)
