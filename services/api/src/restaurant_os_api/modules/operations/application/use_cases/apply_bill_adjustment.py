"""ApplyBillAdjustmentUseCase.

Flat ``POST /api/v1/bills/{id}/adjustments`` -- same coarse/fine
authorization split as every other flat Operations route. Unifies
tips/discounts/service-charges/comps/write-offs into one append-only
ledger (Data Architecture v2.0 Group B), never a separate table per
type.

**Sign convention, applied here rather than left to the caller:**
``discount``/``comp``/``write_off`` are stored as *negative* amounts
(they reduce ``amount_due``); ``service_charge``/``tip`` are stored as
*positive* amounts (they increase it). A caller-supplied ``amount`` is
taken as a magnitude and signed automatically by ``adjustment_type`` --
never trusted as already-signed, so a client can't flip a discount into
a surcharge by sending a positive number.

If ``discount_id`` is supplied instead of a raw ``amount``, the
adjustment amount is computed from ``Discount.compute_amount()``
against the order's own ``subtotal_amount`` (not a caller-supplied
figure at all), and ``Discount.requires_approval`` is enforced -- a
flagged discount applied without ``approved_by_user_id`` raises
``AdjustmentApprovalRequiredError``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import (
    ApplyBillAdjustmentRequestDTO,
    BillDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._bill_mapper import bill_to_dto
from restaurant_os_api.modules.operations.domain.entities import BillAdjustment, BillAdjustmentType
from restaurant_os_api.modules.operations.domain.exceptions import (
    AdjustmentApprovalRequiredError,
    BillAlreadyClosedError,
    BillNotFoundError,
    DiscountNotFoundError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    BillRepository,
    DiscountRepository,
    OrderRepository,
    PaymentRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "billing.manage"

_NEGATIVE_TYPES = {
    BillAdjustmentType.DISCOUNT,
    BillAdjustmentType.COMP,
    BillAdjustmentType.WRITE_OFF,
}


class ApplyBillAdjustmentUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        bill_repository_factory: Callable[[AsyncSession], BillRepository],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        discount_repository_factory: Callable[[AsyncSession], DiscountRepository],
        payment_repository_factory: Callable[[AsyncSession], PaymentRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._bill_repository_factory = bill_repository_factory
        self._order_repository_factory = order_repository_factory
        self._discount_repository_factory = discount_repository_factory
        self._payment_repository_factory = payment_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, request: ApplyBillAdjustmentRequestDTO
    ) -> BillDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            bill_repo = self._bill_repository_factory(uow.session)
            order_repo = self._order_repository_factory(uow.session)
            discount_repo = self._discount_repository_factory(uow.session)
            payment_repo = self._payment_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            bill = await bill_repo.get_by_id(tenant_id, request.bill_id)
            if bill is None:
                raise BillNotFoundError(request.bill_id)
            if bill.status.value == "closed":
                raise BillAlreadyClosedError(bill.id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=bill.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            order = None
            if bill.order_id is not None:
                order = await order_repo.get_by_id(tenant_id, bill.order_id)
                if order is None:
                    raise OrderNotFoundError(bill.order_id)

            adjustment_type = BillAdjustmentType(request.adjustment_type)
            reference_type: str | None = None
            reference_id: str | None = None

            if request.discount_id is not None:
                discount = await discount_repo.get_by_id(tenant_id, request.discount_id)
                if discount is None:
                    raise DiscountNotFoundError(request.discount_id)
                if discount.requires_approval and request.approved_by_user_id is None:
                    raise AdjustmentApprovalRequiredError(discount.id)
                base = order.subtotal_amount if order is not None else Decimal(0)
                magnitude = discount.compute_amount(base)
                reference_type = "discount"
                reference_id = discount.id
            else:
                magnitude = request.amount if request.amount is not None else Decimal(0)

            signed_amount = -magnitude if adjustment_type in _NEGATIVE_TYPES else magnitude

            await bill_repo.add_adjustment(
                BillAdjustment(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    bill_id=bill.id,
                    adjustment_type=adjustment_type,
                    amount=signed_amount,
                    created_at=now,
                    reference_type=reference_type,
                    reference_id=reference_id,
                    reason=request.reason,
                    approved_by_user_id=request.approved_by_user_id,
                )
            )

            tax_lines = (
                await bill_repo.get_tax_lines_for_order(tenant_id, bill.order_id)
                if bill.order_id is not None
                else []
            )
            adjustments = await bill_repo.get_adjustments(tenant_id, bill.id)
            payments = await payment_repo.list_for_bill(tenant_id, bill.id)
            amount_paid = sum(
                (p.amount - p.tip_amount for p in payments if p.status.value == "settled"),
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
