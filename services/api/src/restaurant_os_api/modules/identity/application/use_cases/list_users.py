"""ListUsersUseCase — paginated, tenant-scoped. Same shape as
``ListRolesUseCase``."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import UserListResultDTO
from restaurant_os_api.modules.identity.application.use_cases._user_mapper import user_to_dto
from restaurant_os_api.modules.identity.domain.ports import UserRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListUsersUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
    ) -> None:
        self._session_factory = session_factory
        self._user_repository_factory = user_repository_factory

    async def execute(self, tenant_id: str, *, offset: int, limit: int) -> UserListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            user_repo = self._user_repository_factory(uow.session)
            users, total = await user_repo.list_for_tenant(tenant_id, offset=offset, limit=limit)
        return UserListResultDTO(
            users=[user_to_dto(u) for u in users], total=total, offset=offset, limit=limit
        )
