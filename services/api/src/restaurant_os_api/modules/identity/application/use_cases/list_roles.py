"""ListRolesUseCase — paginated, includes platform-wide roles alongside
the tenant's own (RoleRepository.list_for_tenant's own documented
visibility rule, RBAC Foundation Architecture SS14.2)."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import RoleListResultDTO
from restaurant_os_api.modules.identity.application.use_cases._role_mapper import role_to_dto
from restaurant_os_api.modules.identity.domain.ports import RoleRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListRolesUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        role_repository_factory: Callable[[AsyncSession], RoleRepository],
    ) -> None:
        self._session_factory = session_factory
        self._role_repository_factory = role_repository_factory

    async def execute(self, tenant_id: str, *, offset: int, limit: int) -> RoleListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            role_repo = self._role_repository_factory(uow.session)
            roles, total = await role_repo.list_for_tenant(tenant_id, offset=offset, limit=limit)
        return RoleListResultDTO(
            roles=[role_to_dto(r) for r in roles], total=total, offset=offset, limit=limit
        )
