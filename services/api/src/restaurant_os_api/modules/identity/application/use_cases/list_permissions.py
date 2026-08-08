"""ListPermissionsUseCase — the platform permission catalogue, no
tenant scoping (RBAC Foundation Architecture SS4.2: pure platform
reference data, same as ``currencies``)."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import PermissionDTO
from restaurant_os_api.modules.identity.domain.ports import PermissionRepository
from restaurant_os_api.platform.database import UnitOfWork


class ListPermissionsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        permission_repository_factory: Callable[[AsyncSession], PermissionRepository],
    ) -> None:
        self._session_factory = session_factory
        self._permission_repository_factory = permission_repository_factory

    async def execute(self) -> list[PermissionDTO]:
        async with UnitOfWork(self._session_factory) as uow:
            permission_repo = self._permission_repository_factory(uow.session)
            permissions = await permission_repo.list_active()
        return [
            PermissionDTO(
                code=p.code, module=p.module, description=p.description, is_active=p.is_active
            )
            for p in permissions
        ]
