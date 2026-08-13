"""CloseBranchUseCase -- SS7's ``POST /api/v1/branches/{id}/close``,
mirroring ``suspend``/``reactivate``'s existing sub-resource-verb
pattern. Temporary closure only (``active -> temporarily_closed`` via
``Branch.close_temporarily()``'s own guard) -- ``close_permanently()``
exists on the domain entity but SS7 names no corresponding endpoint,
so it is not exposed here (a disclosed scope boundary, not an
oversight).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import BranchDTO
from restaurant_os_api.modules.restaurant.application.use_cases._branch_mapper import (
    branch_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.events import BranchClosed
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import AddressRepository, BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CloseBranchUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        address_repository_factory: Callable[[AsyncSession], AddressRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._address_repository_factory = address_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, branch_id: str) -> BranchDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            address_repo = self._address_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, branch_id)
            if branch is None:
                raise BranchNotFoundError(branch_id)

            branch.close_temporarily()
            branch = await branch_repo.update(branch)

            address = None
            if branch.address_id is not None:
                address = await address_repo.get_by_id(tenant_id, branch.address_id)

            await outbox.publish(tenant_id, BranchClosed(branch_id=branch.id, occurred_at=now))

        return branch_to_dto(branch, address)
