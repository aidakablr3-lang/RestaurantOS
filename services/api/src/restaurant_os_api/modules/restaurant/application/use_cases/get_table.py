"""GetTableUseCase.

Restaurant Platform Architecture SS7's ``GET /api/v1/branches/
{branch_id}/tables/{id}``. Same cross-branch scoping discipline as
``GetTableZoneUseCase`` -- a table that exists but belongs to a
*different* branch than the URL's own is ``TableNotFoundError``, not
a distinguishable error.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import TableDTO
from restaurant_os_api.modules.restaurant.application.use_cases._table_mapper import table_to_dto
from restaurant_os_api.modules.restaurant.domain.exceptions import TableNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import TableRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetTableUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
    ) -> None:
        self._session_factory = session_factory
        self._table_repository_factory = table_repository_factory

    async def execute(self, tenant_id: str, branch_id: str, table_id: str) -> TableDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            table_repo = self._table_repository_factory(uow.session)
            table = await table_repo.get_by_id(tenant_id, table_id)

        if table is None or table.branch_id != branch_id:
            raise TableNotFoundError(table_id)

        return table_to_dto(table)
