"""CreateTableZoneUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/branches/
{branch_id}/table-zones``. ``branch_id`` is loaded scoped to the
caller's own tenant before anything else -- a branch that exists but
belongs to another tenant is treated identically to one that does not
exist at all (``BranchNotFoundError``, never a distinguishable 403),
the same "belt and suspenders" pattern ``CreateBranchUseCase`` already
established for its own parent-scope check against ``restaurant_id``.

Publishes ``TableZoneCreated`` (SS11's event catalogue names this
event explicitly, unlike ``OperatingHours`` which has none).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateTableZoneRequestDTO,
    TableZoneDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._table_zone_mapper import (
    table_zone_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import TableZone
from restaurant_os_api.modules.restaurant.domain.events import TableZoneCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    TableZoneNameConflictError,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, TableZoneRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateTableZoneUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        table_zone_repository_factory: Callable[[AsyncSession], TableZoneRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._table_zone_repository_factory = table_zone_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: CreateTableZoneRequestDTO) -> TableZoneDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            table_zone_repo = self._table_zone_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            existing = await table_zone_repo.get_by_branch_id_and_name(
                tenant_id, request.branch_id, request.name
            )
            if existing is not None:
                raise TableZoneNameConflictError(request.branch_id, request.name)

            table_zone = await table_zone_repo.create(
                TableZone(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    name=request.name,
                    display_order=request.display_order,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                TableZoneCreated(
                    table_zone_id=table_zone.id,
                    branch_id=table_zone.branch_id,
                    name=table_zone.name,
                    occurred_at=now,
                ),
            )

        return table_zone_to_dto(table_zone)
