"""GetRoleUseCase."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import RoleDTO
from restaurant_os_api.modules.identity.application.use_cases._role_mapper import role_to_dto
from restaurant_os_api.modules.identity.domain.exceptions import RoleNotFoundError
from restaurant_os_api.modules.identity.domain.ports import RoleRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetRoleUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        role_repository_factory: Callable[[AsyncSession], RoleRepository],
    ) -> None:
        self._session_factory = session_factory
        self._role_repository_factory = role_repository_factory

    async def execute(self, tenant_id: str, role_id: str) -> RoleDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            role_repo = self._role_repository_factory(uow.session)
            role = await role_repo.get_by_id(tenant_id, role_id)
        if role is None:
            raise RoleNotFoundError(role_id)
        return role_to_dto(role)
