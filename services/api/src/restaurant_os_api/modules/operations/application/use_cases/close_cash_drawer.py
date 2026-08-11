"""CloseCashDrawerUseCase.

Flat ``POST /api/v1/cash-drawers/{id}/close`` -- same coarse/fine
authorization split as every other flat Operations route. The
Blueprint's "daily cash-up automatically reconciled against POS sales"
story: ``expected_cash_amount`` = opening float + every settled cash
Payment recorded at this branch since the drawer opened; the variance
against the counted amount is computed here, not stored (a pure
read-time reconciliation figure, not a second source of truth).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import (
    CashDrawerDTO,
    CloseCashDrawerRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._cash_drawer_mapper import (
    cash_drawer_to_dto,
)
from restaurant_os_api.modules.operations.domain.exceptions import CashDrawerNotFoundError
from restaurant_os_api.modules.operations.domain.ports import CashDrawerRepository
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "billing.manage"


class CloseCashDrawerUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        cash_drawer_repository_factory: Callable[[AsyncSession], CashDrawerRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._cash_drawer_repository_factory = cash_drawer_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, request: CloseCashDrawerRequestDTO
    ) -> CashDrawerDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            cash_drawer_repo = self._cash_drawer_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            cash_drawer = await cash_drawer_repo.get_by_id(tenant_id, request.cash_drawer_id)
            if cash_drawer is None:
                raise CashDrawerNotFoundError(request.cash_drawer_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=cash_drawer.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            settled_cash = await cash_drawer_repo.sum_settled_cash_payments(
                tenant_id, cash_drawer.branch_id, since=cash_drawer.opened_at
            )
            expected_cash_amount = cash_drawer.opening_float_amount + settled_cash

            cash_drawer.close(closing_counted_amount=request.closing_counted_amount, closed_at=now)
            cash_drawer = await cash_drawer_repo.update(cash_drawer)

        return cash_drawer_to_dto(cash_drawer, expected_cash_amount=expected_cash_amount)
