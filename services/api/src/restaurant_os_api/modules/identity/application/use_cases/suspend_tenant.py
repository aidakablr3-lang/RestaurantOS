"""SuspendTenantUseCase.

Data Architecture v2.0 SS4.5: "the tenant's data is untouched, but the
Auth layer rejects new sessions" — enforced two ways here, both in the
same transaction as the status change: existing sessions are revoked
outright (so an already-issued access token stops working the moment
its live tenant-status check runs, per Commit 4's
``VerifyAccessTokenUseCase``), and the Tenant Directory entry is kept in
sync so any future directory-based routing decision sees the same
status immediately.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import TenantDTO
from restaurant_os_api.modules.identity.application.use_cases._tenant_mapper import tenant_to_dto
from restaurant_os_api.modules.identity.domain.events import TenantSuspended
from restaurant_os_api.modules.identity.domain.exceptions import TenantNotFoundError
from restaurant_os_api.modules.identity.domain.ports import (
    SessionRepository,
    TenantDirectoryRepository,
    TenantRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class SuspendTenantUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_repository_factory: Callable[[AsyncSession], TenantRepository],
        session_repository_factory: Callable[[AsyncSession], SessionRepository],
        directory_repository_factory: Callable[[AsyncSession], TenantDirectoryRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._tenant_repository_factory = tenant_repository_factory
        self._session_repository_factory = session_repository_factory
        self._directory_repository_factory = directory_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str) -> TenantDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            tenant_repo = self._tenant_repository_factory(uow.session)
            session_repo = self._session_repository_factory(uow.session)
            directory_repo = self._directory_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            tenant = await tenant_repo.get_by_id(tenant_id)
            if tenant is None:
                raise TenantNotFoundError(tenant_id)

            tenant.suspend()  # raises InvalidTenantStatusTransitionError if illegal
            tenant = await tenant_repo.update(tenant)
            await directory_repo.update_status(tenant_id, tenant.status.value)
            await session_repo.revoke_all_for_tenant(tenant_id)
            await outbox.publish(
                tenant_id, TenantSuspended(tenant_id=tenant_id, occurred_at=datetime.now(UTC))
            )

        return tenant_to_dto(tenant)
