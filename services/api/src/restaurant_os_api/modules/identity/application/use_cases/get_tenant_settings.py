"""GetTenantSettingsUseCase."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import SystemSettingDTO
from restaurant_os_api.modules.identity.domain.ports import SystemSettingRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetTenantSettingsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        system_setting_repository_factory: Callable[[AsyncSession], SystemSettingRepository],
    ) -> None:
        self._session_factory = session_factory
        self._system_setting_repository_factory = system_setting_repository_factory

    async def execute(self, tenant_id: str) -> list[SystemSettingDTO]:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            settings_repo = self._system_setting_repository_factory(uow.session)
            settings = await settings_repo.list_for_tenant(tenant_id)
        return [SystemSettingDTO(key=s.key, value=s.value, branch_id=s.branch_id) for s in settings]
