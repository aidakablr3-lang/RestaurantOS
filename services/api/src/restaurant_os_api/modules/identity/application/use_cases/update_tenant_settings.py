"""UpdateTenantSettingsUseCase.

Always creates a branch-less (tenant-wide) setting — ``branch_id`` stays
``None`` this sprint, per the module's explicit Branch-does-not-exist-yet
scope boundary (Data Architecture v2.0 SS3.14).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.dto import (
    SystemSettingDTO,
    UpdateSettingRequestDTO,
)
from restaurant_os_api.modules.identity.domain.entities import SystemSetting
from restaurant_os_api.modules.identity.domain.ports import SystemSettingRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateTenantSettingsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        system_setting_repository_factory: Callable[[AsyncSession], SystemSettingRepository],
    ) -> None:
        self._session_factory = session_factory
        self._system_setting_repository_factory = system_setting_repository_factory

    async def execute(self, request: UpdateSettingRequestDTO) -> SystemSettingDTO:
        async with UnitOfWork(self._session_factory, TenantContext(request.tenant_id)) as uow:
            settings_repo = self._system_setting_repository_factory(uow.session)
            setting = await settings_repo.upsert(
                SystemSetting(
                    id=generate_ulid(),
                    tenant_id=request.tenant_id,
                    key=request.key,
                    value=request.value,
                    # The row's real `created_at` is the database's own
                    # `server_default=func.now()`, set once on first
                    # insert and left untouched on conflict (the
                    # repository's upsert only ever writes `value` on
                    # conflict) — this value is never persisted, it only
                    # satisfies the entity's required field honestly.
                    created_at=datetime.now(UTC),
                )
            )
        return SystemSettingDTO(key=setting.key, value=setting.value, branch_id=setting.branch_id)
