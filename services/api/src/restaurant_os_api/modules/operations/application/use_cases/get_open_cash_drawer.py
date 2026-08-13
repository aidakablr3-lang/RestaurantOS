"""GetOpenCashDrawerUseCase.

``GET /api/v1/branches/{branch_id}/cash-drawers/open`` -- the lookup
that was previously missing entirely (the collection route only ever
supported POST). Without this, the Cash Drawer page could only track
whatever drawer it itself opened, in local browser state, lost on
reload -- there was no way to recover "is a drawer currently open for
this branch, and if so which one" after a refresh.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import CashDrawerDTO
from restaurant_os_api.modules.operations.application.use_cases._cash_drawer_mapper import (
    cash_drawer_to_dto,
)
from restaurant_os_api.modules.operations.domain.ports import CashDrawerRepository
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "billing.read"


class GetOpenCashDrawerUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        cash_drawer_repository_factory: Callable[[AsyncSession], CashDrawerRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._cash_drawer_repository_factory = cash_drawer_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(self, tenant_id: str, user_id: str, branch_id: str) -> CashDrawerDTO | None:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            cash_drawer_repo = self._cash_drawer_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, branch_id)
            if branch is None:
                raise BranchNotFoundError(branch_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            cash_drawer = await cash_drawer_repo.get_open_for_branch(tenant_id, branch_id)
            return cash_drawer_to_dto(cash_drawer) if cash_drawer is not None else None
