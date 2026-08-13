"""CreateTableUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/branches/
{branch_id}/tables``. ``branch_id`` is loaded scoped to the caller's
own tenant first (mirrors ``CreateTableZoneUseCase``'s own check),
then ``table_zone_id`` is loaded and verified to belong to *that same*
branch -- a table zone that exists but belongs to a different branch
(or a different tenant, or doesn't exist at all) is
``TableZoneNotFoundError``, the same cross-scope-is-404 discipline
Step 4.4 established.

A new table always starts ``TableStatus.AVAILABLE`` (the DB's own
``server_default``) -- SS7 gives status changes their own dedicated
endpoint, never a client-supplied value on create. ``sync_version``
starts at its column default (``0``); per Step 4.0's Decision Lock,
no optimistic-concurrency code is written this sprint, so this use
case never reads or reasons about it beyond that initial value.

Publishes ``TableCreated`` (SS11 names this event explicitly).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import CreateTableRequestDTO, TableDTO
from restaurant_os_api.modules.restaurant.application.use_cases._table_mapper import table_to_dto
from restaurant_os_api.modules.restaurant.domain.entities import Table, TableStatus
from restaurant_os_api.modules.restaurant.domain.events import TableCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    TableNumberConflictError,
    TableZoneNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    TableRepository,
    TableZoneRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateTableUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        table_zone_repository_factory: Callable[[AsyncSession], TableZoneRepository],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._table_zone_repository_factory = table_zone_repository_factory
        self._table_repository_factory = table_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: CreateTableRequestDTO) -> TableDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            table_zone_repo = self._table_zone_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            table_zone = await table_zone_repo.get_by_id(tenant_id, request.table_zone_id)
            if table_zone is None or table_zone.branch_id != request.branch_id:
                raise TableZoneNotFoundError(request.table_zone_id)

            existing = await table_repo.get_by_branch_id_and_table_number(
                tenant_id, request.branch_id, request.table_number
            )
            if existing is not None:
                raise TableNumberConflictError(request.branch_id, request.table_number)

            table = await table_repo.create(
                Table(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    table_zone_id=request.table_zone_id,
                    table_number=request.table_number,
                    capacity=request.capacity,
                    status=TableStatus.AVAILABLE,
                    sync_version=0,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                TableCreated(
                    table_id=table.id,
                    branch_id=table.branch_id,
                    table_zone_id=table.table_zone_id,
                    table_number=table.table_number,
                    occurred_at=now,
                ),
            )

        return table_to_dto(table)
