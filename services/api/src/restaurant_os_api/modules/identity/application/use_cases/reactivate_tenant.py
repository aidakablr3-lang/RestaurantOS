"""ReactivateTenantUseCase.

Unlike suspend/offboard, reactivation does not revoke sessions — it
restores access, so there is nothing to revoke. Users who were logged
in before the suspension still hold access tokens whose live
tenant-status check (Commit 4) will now pass again on their next
request; they are not silently re-authenticated with a fresh session
they never asked for.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import TenantDTO
from restaurant_os_api.modules.identity.application.use_cases._tenant_mapper import tenant_to_dto
from restaurant_os_api.modules.identity.domain.events import TenantReactivated
from restaurant_os_api.modules.identity.domain.exceptions import TenantNotFoundError
from restaurant_os_api.modules.identity.domain.ports import (
    TenantDirectoryRepository,
    TenantRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class ReactivateTenantUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_repository_factory: Callable[[AsyncSession], TenantRepository],
        directory_repository_factory: Callable[[AsyncSession], TenantDirectoryRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._tenant_repository_factory = tenant_repository_factory
        self._directory_repository_factory = directory_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str) -> TenantDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            tenant_repo = self._tenant_repository_factory(uow.session)
            directory_repo = self._directory_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            tenant = await tenant_repo.get_by_id(tenant_id)
            if tenant is None:
                raise TenantNotFoundError(tenant_id)

            tenant.reactivate()  # raises InvalidTenantStatusTransitionError if illegal
            tenant = await tenant_repo.update(tenant)
            await directory_repo.update_status(tenant_id, tenant.status.value)
            await outbox.publish(
                tenant_id, TenantReactivated(tenant_id=tenant_id, occurred_at=datetime.now(UTC))
            )

        return tenant_to_dto(tenant)
