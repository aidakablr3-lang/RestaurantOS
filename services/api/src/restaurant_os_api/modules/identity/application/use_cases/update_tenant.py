"""UpdateTenantUseCase — display name and metadata only.

Deliberately narrow: ``legal_name``, ``tenant_tier``, and ``status`` are
not editable through this use case. Legal name changes and tier
migrations are significant enough events to warrant their own explicit
operations (and, for tier, the not-yet-built migration workflow —
Data Architecture v2.0 SS4.5); status changes go through the dedicated
suspend/reactivate/offboard use cases so every transition is checked
against ``Tenant``'s legal-transition guard, never bypassed via a
generic update.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import TenantDTO, UpdateTenantRequestDTO
from restaurant_os_api.modules.identity.application.use_cases._tenant_mapper import tenant_to_dto
from restaurant_os_api.modules.identity.domain.exceptions import TenantNotFoundError
from restaurant_os_api.modules.identity.domain.ports import TenantRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateTenantUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_repository_factory: Callable[[AsyncSession], TenantRepository],
    ) -> None:
        self._session_factory = session_factory
        self._tenant_repository_factory = tenant_repository_factory

    async def execute(self, request: UpdateTenantRequestDTO) -> TenantDTO:
        async with UnitOfWork(self._session_factory, TenantContext(request.tenant_id)) as uow:
            tenant_repo = self._tenant_repository_factory(uow.session)
            tenant = await tenant_repo.get_by_id(request.tenant_id)
            if tenant is None:
                raise TenantNotFoundError(request.tenant_id)
            tenant.display_name = request.display_name
            tenant.metadata = request.metadata
            tenant = await tenant_repo.update(tenant)
        return tenant_to_dto(tenant)
