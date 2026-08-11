"""ListPaymentsUseCase. ``GET /api/v1/bills/{id}/payments``."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import PaymentDTO
from restaurant_os_api.modules.operations.application.use_cases._payment_mapper import (
    payment_to_dto,
)
from restaurant_os_api.modules.operations.domain.exceptions import BillNotFoundError
from restaurant_os_api.modules.operations.domain.ports import BillRepository, PaymentRepository
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "billing.read"


class ListPaymentsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        bill_repository_factory: Callable[[AsyncSession], BillRepository],
        payment_repository_factory: Callable[[AsyncSession], PaymentRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._bill_repository_factory = bill_repository_factory
        self._payment_repository_factory = payment_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(self, tenant_id: str, user_id: str, bill_id: str) -> list[PaymentDTO]:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            bill_repo = self._bill_repository_factory(uow.session)
            payment_repo = self._payment_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            bill = await bill_repo.get_by_id(tenant_id, bill_id)
            if bill is None:
                raise BillNotFoundError(bill_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=bill.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            payments = await payment_repo.list_for_bill(tenant_id, bill.id)

        return [payment_to_dto(p) for p in payments]
