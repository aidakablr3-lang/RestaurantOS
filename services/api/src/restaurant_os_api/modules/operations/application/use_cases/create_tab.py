"""CreateTabUseCase.

``POST /api/v1/branches/{branch_id}/tabs`` -- branch-nested, gated the
same ``order.manage``/``order.read`` permissions as Order itself (Tab
has no separate RBAC permission code -- it's part of Order Management,
Architecture doc SS10).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import CreateTabRequestDTO, TabDTO
from restaurant_os_api.modules.operations.application.use_cases._tab_mapper import tab_to_dto
from restaurant_os_api.modules.operations.domain.entities import Tab, TabStatus
from restaurant_os_api.modules.operations.domain.ports import TabRepository
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    TableNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, TableRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class CreateTabUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        tab_repository_factory: Callable[[AsyncSession], TabRepository],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._table_repository_factory = table_repository_factory
        self._tab_repository_factory = tab_repository_factory

    async def execute(self, tenant_id: str, request: CreateTabRequestDTO) -> TabDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)
            tab_repo = self._tab_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            if request.table_id is not None:
                table = await table_repo.get_by_id(tenant_id, request.table_id)
                if table is None or table.branch_id != request.branch_id:
                    raise TableNotFoundError(request.table_id)

            tab = await tab_repo.create(
                Tab(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    status=TabStatus.OPEN,
                    opened_at=now,
                    created_at=now,
                    table_id=request.table_id,
                )
            )

        return tab_to_dto(tab)
