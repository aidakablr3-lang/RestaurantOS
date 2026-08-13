"""GetBillUseCase. ``GET /api/v1/bills/{id}`` -- flat, gated
``billing.read`` at any scope + fine-grained branch resolution.

``amount_paid`` is the sum of every settled payment's full ``amount``
-- tip is not part of bill settlement (P0 correction, 2026-08-12), so
nothing is subtracted from a payment's amount here."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import BillDTO
from restaurant_os_api.modules.operations.application.use_cases._bill_mapper import bill_to_dto
from restaurant_os_api.modules.operations.domain.entities import PaymentStatus
from restaurant_os_api.modules.operations.domain.exceptions import BillNotFoundError
from restaurant_os_api.modules.operations.domain.ports import (
    BillRepository,
    OrderRepository,
    PaymentRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "billing.read"


class GetBillUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        bill_repository_factory: Callable[[AsyncSession], BillRepository],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        payment_repository_factory: Callable[[AsyncSession], PaymentRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._bill_repository_factory = bill_repository_factory
        self._order_repository_factory = order_repository_factory
        self._payment_repository_factory = payment_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(self, tenant_id: str, user_id: str, bill_id: str) -> BillDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            bill_repo = self._bill_repository_factory(uow.session)
            order_repo = self._order_repository_factory(uow.session)
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

            order = await order_repo.get_by_id(tenant_id, bill.order_id) if bill.order_id else None
            tax_lines = (
                await bill_repo.get_tax_lines_for_order(tenant_id, bill.order_id)
                if bill.order_id
                else []
            )
            adjustments = await bill_repo.get_adjustments(tenant_id, bill.id)
            payments = await payment_repo.list_for_bill(tenant_id, bill.id)
            amount_paid = sum(
                (p.amount for p in payments if p.status == PaymentStatus.SETTLED),
                Decimal(0),
            )

        return bill_to_dto(
            bill,
            subtotal_amount=order.subtotal_amount if order is not None else Decimal(0),
            tax_amount=order.tax_amount if order is not None else Decimal(0),
            tax_lines=tax_lines,
            adjustments=adjustments,
            amount_paid=amount_paid,
        )
