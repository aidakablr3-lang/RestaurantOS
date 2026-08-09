"""CreateQRCodeUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/tables/{id}/
qr-codes`` -- "Generates a new active code, revokes the prior one."
Like ``ChangeTableStatusUseCase`` (Step 4.5), this route's own path is
flat (no ``branch_id``), so it reuses Step 4.0 Decision 3's
``resolve_and_authorize_branch`` exactly the same way: load the table
first (tenant-scoped only) to discover its own ``branch_id``, then
authorize against that branch via the caller's resolved grants. The
coarse router gate is ``require_permission_at_any_scope("table.manage")``;
this use case makes the real, resource-specific decision.

The token is generated via ``core.ids.generate_qr_token()`` --
cryptographically random and non-sequential per ADR 0001, never the
row's own ULID ``id``.

Only the authenticated management path is implemented here (Step
4.6). The unauthenticated guest-resolution endpoint
(``GET /api/v1/qr/{token}``) and its ADR-0001-mandated rate-limiting/
abuse-monitoring requirements are explicitly deferred to a separate
step per the user's own scope decision -- nothing in this use case
builds toward or assumes that infrastructure exists.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_qr_token, generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.application.dto import QRCodeDTO
from restaurant_os_api.modules.restaurant.application.use_cases._qr_code_mapper import (
    qr_code_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import QRCode, QRCodeStatus
from restaurant_os_api.modules.restaurant.domain.events import QRCodeGenerated, QRCodeRevoked
from restaurant_os_api.modules.restaurant.domain.exceptions import TableNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    QRCodeRepository,
    TableRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "table.manage"


class CreateQRCodeUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        qr_code_repository_factory: Callable[[AsyncSession], QRCodeRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._table_repository_factory = table_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._qr_code_repository_factory = qr_code_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, user_id: str, table_id: str) -> QRCodeDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            table_repo = self._table_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            qr_code_repo = self._qr_code_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            table = await table_repo.get_by_id(tenant_id, table_id)
            if table is None:
                raise TableNotFoundError(table_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=table.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            existing_codes = await qr_code_repo.list_for_table(tenant_id, table_id)
            active_code = next((c for c in existing_codes if c.status == QRCodeStatus.ACTIVE), None)
            if active_code is not None:
                active_code.revoke()
                await qr_code_repo.update(active_code)
                await outbox.publish(
                    tenant_id,
                    QRCodeRevoked(qr_code_id=active_code.id, table_id=table_id, occurred_at=now),
                )

            new_code = await qr_code_repo.create(
                QRCode(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=table.branch_id,
                    table_id=table_id,
                    token=generate_qr_token(),
                    status=QRCodeStatus.ACTIVE,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                QRCodeGenerated(qr_code_id=new_code.id, table_id=table_id, occurred_at=now),
            )

        return qr_code_to_dto(new_code)
