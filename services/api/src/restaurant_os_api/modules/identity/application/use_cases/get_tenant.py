"""GetTenantUseCase — platform-admin lookup of any tenant by id."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import TenantDTO
from restaurant_os_api.modules.identity.application.use_cases._tenant_mapper import tenant_to_dto
from restaurant_os_api.modules.identity.domain.exceptions import TenantNotFoundError
from restaurant_os_api.modules.identity.domain.ports import TenantRepository
from restaurant_os_api.platform.database import UnitOfWork


class GetTenantUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_repository_factory: Callable[[AsyncSession], TenantRepository],
    ) -> None:
        self._session_factory = session_factory
        self._tenant_repository_factory = tenant_repository_factory

    async def execute(self, tenant_id: str) -> TenantDTO:
        # No TenantContext: `tenants` carries no RLS policy (it is the
        # scoping root, Data Architecture v2.0 SS5.2), and a platform
        # admin's lookup is not itself scoped to any one tenant.
        async with UnitOfWork(self._session_factory) as uow:
            tenant_repo = self._tenant_repository_factory(uow.session)
            tenant = await tenant_repo.get_by_id(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id)
        return tenant_to_dto(tenant)
