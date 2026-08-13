"""ChangeTableStatusUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/tables/{id}/
status`` -- the one Table route architecture puts at a *flat* path
("the one endpoint a future Edge app's sync engine will eventually
call through ``/sync/push`` instead of this direct path"), unlike
every other Table/TableZone route, which is nested under
``branch_id``. A flat path means there is no ``branch_id`` in the URL
for a router-level ``require_branch_permission`` gate to read.

Rather than inventing a new authorization mechanism for this one
route, this reuses Step 4.0 Decision 3's ``resolve_and_authorize_branch``
exactly as it was built for: "a branch identifier that arrives
somewhere other than the URL path" -- here, discovered by loading the
table first (tenant-scoped only) and resolving *its own* ``branch_id``,
then checking the caller's own resolved grants against that specific
branch. The router gates coarsely with
``require_permission_at_any_scope("table.manage")`` (holds the
permission *somewhere* at all); this use case makes the real,
resource-specific decision -- the same "coarse router gate,
fine-grained use-case decision" split ``ListAccessibleBranchesUseCase``
already established.

Publishes ``TableStatusChanged`` -- Architecture SS11 keeps this
separate from ``TableUpdated`` deliberately (a future WebSocket
floor-plan consumer subscribes to status alone). No status-transition
graph is enforced: architecture SS3.1 constrains ``status`` to one of
four values (a value constraint) but names no transition rules, and
the pre-existing Step 3 ``Table`` domain entity has no guard methods
(unlike ``Branch``'s ``activate()``/``close()``/``reopen()``) --
inventing one here would be exactly the kind of unspecified business
rule the architecture's own review process has consistently avoided
for this module. Disclosed as a known limitation, not silently
decided.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.application.dto import (
    ChangeTableStatusRequestDTO,
    TableDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._table_mapper import table_to_dto
from restaurant_os_api.modules.restaurant.domain.entities import TableStatus
from restaurant_os_api.modules.restaurant.domain.events import TableStatusChanged
from restaurant_os_api.modules.restaurant.domain.exceptions import TableNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, TableRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "table.manage"


class ChangeTableStatusUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._table_repository_factory = table_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, user_id: str, request: ChangeTableStatusRequestDTO
    ) -> TableDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            table_repo = self._table_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            table = await table_repo.get_by_id(tenant_id, request.table_id)
            if table is None:
                raise TableNotFoundError(request.table_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=table.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            previous_status = table.status
            table.status = TableStatus(request.status)
            table = await table_repo.update(table)

            await outbox.publish(
                tenant_id,
                TableStatusChanged(
                    table_id=table.id,
                    previous_status=previous_status.value,
                    new_status=table.status.value,
                    occurred_at=now,
                ),
            )

        return table_to_dto(table)
