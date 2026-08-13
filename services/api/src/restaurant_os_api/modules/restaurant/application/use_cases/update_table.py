"""UpdateTableUseCase.

Restaurant Platform Architecture SS7's ``PATCH /api/v1/branches/
{branch_id}/tables/{id}`` -- non-status edits only (``table_zone_id``,
``table_number``, ``capacity``). ``status`` has its own dedicated
endpoint (SS7's explicit split) and is never touched here.

Same cross-branch scoping discipline as ``GetTableUseCase``: a table
belonging to a different branch than the URL's own is
``TableNotFoundError``. If ``table_zone_id`` changes, the new zone is
re-verified to belong to the *same* branch as the table itself --
identical to the check ``CreateTableUseCase`` already performs.

Publishes ``TableUpdated`` -- Architecture SS11 explicitly separates
this from ``TableStatusChanged`` (see ``change_table_status.py``).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import TableDTO, UpdateTableRequestDTO
from restaurant_os_api.modules.restaurant.application.use_cases._table_mapper import table_to_dto
from restaurant_os_api.modules.restaurant.domain.events import TableUpdated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    TableNotFoundError,
    TableNumberConflictError,
    TableZoneNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import TableRepository, TableZoneRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateTableUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        table_zone_repository_factory: Callable[[AsyncSession], TableZoneRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._table_repository_factory = table_repository_factory
        self._table_zone_repository_factory = table_zone_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: UpdateTableRequestDTO) -> TableDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            table_repo = self._table_repository_factory(uow.session)
            table_zone_repo = self._table_zone_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            table = await table_repo.get_by_id(tenant_id, request.table_id)
            if table is None or table.branch_id != request.branch_id:
                raise TableNotFoundError(request.table_id)

            if request.table_zone_id != table.table_zone_id:
                table_zone = await table_zone_repo.get_by_id(tenant_id, request.table_zone_id)
                if table_zone is None or table_zone.branch_id != table.branch_id:
                    raise TableZoneNotFoundError(request.table_zone_id)
                table.table_zone_id = request.table_zone_id

            if request.table_number != table.table_number:
                existing = await table_repo.get_by_branch_id_and_table_number(
                    tenant_id, table.branch_id, request.table_number
                )
                if existing is not None and existing.id != table.id:
                    raise TableNumberConflictError(table.branch_id, request.table_number)
                table.table_number = request.table_number

            table.capacity = request.capacity

            table = await table_repo.update(table)

            await outbox.publish(tenant_id, TableUpdated(table_id=table.id, occurred_at=now))

        return table_to_dto(table)
