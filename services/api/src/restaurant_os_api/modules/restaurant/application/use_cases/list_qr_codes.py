"""ListQRCodesUseCase.

Restaurant Platform Architecture SS7's ``GET /api/v1/tables/{id}/
qr-codes`` -- regeneration history for a table, newest first
(``QRCodeRepository.list_for_table``'s own pre-existing ``ORDER BY
created_at DESC``, unchanged here). Same flat-path authorization shape
as ``CreateQRCodeUseCase``: loads the table first, then reuses
``resolve_and_authorize_branch`` against its ``branch_id``.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from restaurant_os_api.modules.restaurant.domain.exceptions import TableNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    QRCodeRepository,
    TableRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "table.read"


class ListQRCodesUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        qr_code_repository_factory: Callable[[AsyncSession], QRCodeRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._table_repository_factory = table_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._qr_code_repository_factory = qr_code_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(self, tenant_id: str, user_id: str, table_id: str) -> list[QRCodeDTO]:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            table_repo = self._table_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            qr_code_repo = self._qr_code_repository_factory(uow.session)

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

            codes = await qr_code_repo.list_for_table(tenant_id, table_id)

        return [qr_code_to_dto(c) for c in codes]
