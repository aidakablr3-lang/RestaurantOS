"""ListTenantsUseCase — platform-admin paginated tenant directory."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import (
    ListTenantsRequestDTO,
    TenantListResultDTO,
)
from restaurant_os_api.modules.identity.application.use_cases._tenant_mapper import tenant_to_dto
from restaurant_os_api.modules.identity.domain.entities import TenantStatus
from restaurant_os_api.modules.identity.domain.ports import TenantRepository
from restaurant_os_api.platform.database import UnitOfWork


class ListTenantsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_repository_factory: Callable[[AsyncSession], TenantRepository],
    ) -> None:
        self._session_factory = session_factory
        self._tenant_repository_factory = tenant_repository_factory

    async def execute(self, request: ListTenantsRequestDTO) -> TenantListResultDTO:
        status_filter = TenantStatus(request.status) if request.status is not None else None
        async with UnitOfWork(self._session_factory) as uow:
            tenant_repo = self._tenant_repository_factory(uow.session)
            tenants, total = await tenant_repo.list(
                offset=request.offset, limit=request.limit, status=status_filter
            )
        return TenantListResultDTO(
            tenants=[tenant_to_dto(t) for t in tenants],
            total=total,
            offset=request.offset,
            limit=request.limit,
        )
