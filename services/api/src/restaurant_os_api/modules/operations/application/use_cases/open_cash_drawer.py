"""OpenCashDrawerUseCase.

``POST /api/v1/branches/{branch_id}/cash-drawers`` -- branch-nested,
gated ``require_branch_permission("billing.manage")``. At most one open
drawer per branch at a time -- opening a second is rejected
(``CashDrawerAlreadyOpenError``) rather than leaving "which drawer is
this cash payment against" ambiguous.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import (
    CashDrawerDTO,
    OpenCashDrawerRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._cash_drawer_mapper import (
    cash_drawer_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import CashDrawer, CashDrawerStatus
from restaurant_os_api.modules.operations.domain.exceptions import CashDrawerAlreadyOpenError
from restaurant_os_api.modules.operations.domain.ports import CashDrawerRepository
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class OpenCashDrawerUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        cash_drawer_repository_factory: Callable[[AsyncSession], CashDrawerRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
    ) -> None:
        self._session_factory = session_factory
        self._cash_drawer_repository_factory = cash_drawer_repository_factory
        self._branch_repository_factory = branch_repository_factory

    async def execute(self, tenant_id: str, request: OpenCashDrawerRequestDTO) -> CashDrawerDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            cash_drawer_repo = self._cash_drawer_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            existing_open = await cash_drawer_repo.get_open_for_branch(tenant_id, request.branch_id)
            if existing_open is not None:
                raise CashDrawerAlreadyOpenError(request.branch_id)

            cash_drawer = await cash_drawer_repo.create(
                CashDrawer(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    status=CashDrawerStatus.OPEN,
                    opening_float_amount=request.opening_float_amount,
                    opened_at=now,
                    created_at=now,
                    terminal_id=request.terminal_id,
                )
            )
        return cash_drawer_to_dto(cash_drawer)
