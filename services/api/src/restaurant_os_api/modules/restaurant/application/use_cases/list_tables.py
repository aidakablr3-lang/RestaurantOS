"""ListTablesUseCase -- branch-scoped, offset/limit paginated,
deterministic ordering by ``table_number``
(``TableRepository.list_for_branch``'s own ``ORDER BY``, pre-existing
Step 3 code, unchanged here).

``branch_id`` is verified to exist (scoped to the caller's tenant)
before listing, mirroring ``ListTableZonesUseCase``'s own check.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import TableListResultDTO
from restaurant_os_api.modules.restaurant.application.use_cases._table_mapper import table_to_dto
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, TableRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListTablesUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._table_repository_factory = table_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> TableListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, branch_id)
            if branch is None:
                raise BranchNotFoundError(branch_id)

            tables, total = await table_repo.list_for_branch(
                tenant_id, branch_id, offset=offset, limit=limit
            )

        return TableListResultDTO(
            tables=[table_to_dto(t) for t in tables], total=total, offset=offset, limit=limit
        )
