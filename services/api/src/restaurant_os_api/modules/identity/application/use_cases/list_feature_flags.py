"""ListFeatureFlagsUseCase.

Resolves every flag *visible* to a tenant (its own overrides plus every
platform-wide flag) down to one effective boolean per key — deduplicating
so a key that has both a platform-wide row and a tenant-specific
override appears exactly once, with the override winning (``FeatureFlag
.is_effective_for`` is evaluated per row; the tenant-specific row for a
given key takes precedence over the platform-wide row of the same key).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import FeatureFlagStatusDTO
from restaurant_os_api.modules.identity.domain.ports import FeatureFlagRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListFeatureFlagsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        feature_flag_repository_factory: Callable[[AsyncSession], FeatureFlagRepository],
    ) -> None:
        self._session_factory = session_factory
        self._feature_flag_repository_factory = feature_flag_repository_factory

    async def execute(self, tenant_id: str) -> list[FeatureFlagStatusDTO]:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            flag_repo = self._feature_flag_repository_factory(uow.session)
            flags = await flag_repo.list_effective_for_tenant(tenant_id)

        # A tenant-specific row (tenant_id is not None) wins over a
        # platform-wide row of the same key — sort so the tenant-specific
        # row is seen last and overwrites the dict entry.
        by_key = {}
        for flag in sorted(flags, key=lambda f: f.tenant_id is not None):
            by_key[flag.key] = flag

        return [
            FeatureFlagStatusDTO(key=key, enabled=flag.is_effective_for(tenant_id))
            for key, flag in by_key.items()
        ]
