"""ListTaxesUseCase.

``GET /api/v1/taxes`` -- tenant-wide, flat, mirrors ``CreateTaxUseCase``'s
own shape. Returns every active tax for the tenant; the Taxes page was
previously create-only because no list endpoint existed at all.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.domain.entities import Tax
from restaurant_os_api.modules.operations.domain.ports import TaxRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListTaxesUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tax_repository_factory: Callable[[AsyncSession], TaxRepository],
    ) -> None:
        self._session_factory = session_factory
        self._tax_repository_factory = tax_repository_factory

    async def execute(self, tenant_id: str) -> list[Tax]:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            tax_repo = self._tax_repository_factory(uow.session)
            return await tax_repo.list_active_for_tenant(tenant_id)
