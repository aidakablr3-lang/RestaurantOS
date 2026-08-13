"""CreateTaxUseCase.

``POST /api/v1/taxes`` -- tenant-wide, mirrors ``CreateModifierGroupUseCase``'s
own flat, tenant-scoped shape (no branch dimension, gated
``require_permission("billing.manage")`` tenant-wide, not
``require_branch_permission``).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.domain.entities import Tax
from restaurant_os_api.modules.operations.domain.ports import TaxRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class CreateTaxUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tax_repository_factory: Callable[[AsyncSession], TaxRepository],
    ) -> None:
        self._session_factory = session_factory
        self._tax_repository_factory = tax_repository_factory

    async def execute(self, tenant_id: str, name: str, rate: str) -> Tax:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            tax_repo = self._tax_repository_factory(uow.session)
            tax = await tax_repo.create(
                Tax(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    name=name,
                    rate=Decimal(rate),
                    is_active=True,
                    created_at=now,
                )
            )
        return tax
