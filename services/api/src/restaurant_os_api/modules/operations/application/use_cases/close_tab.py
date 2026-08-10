"""CloseTabUseCase.

Flat ``POST /api/v1/tabs/{id}/close`` -- same coarse/fine-grained split
as ``FireOrderUseCase``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import TabDTO
from restaurant_os_api.modules.operations.application.use_cases._tab_mapper import tab_to_dto
from restaurant_os_api.modules.operations.domain.exceptions import TabNotFoundError
from restaurant_os_api.modules.operations.domain.ports import TabRepository
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "order.manage"


class CloseTabUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tab_repository_factory: Callable[[AsyncSession], TabRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._tab_repository_factory = tab_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(self, tenant_id: str, user_id: str, tab_id: str) -> TabDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            tab_repo = self._tab_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            tab = await tab_repo.get_by_id(tenant_id, tab_id)
            if tab is None:
                raise TabNotFoundError(tab_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=tab.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            tab.close(closed_at=now)
            tab = await tab_repo.update(tab)

        return tab_to_dto(tab)
