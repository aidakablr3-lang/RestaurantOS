"""RequestRefundUseCase.

Flat ``POST /api/v1/payments/{id}/refund`` -- gated by its own,
separate permission (``billing.refund``, distinct from
``billing.manage`` -- Architecture doc SS10: "can take payments should
not silently imply can reverse them").

``approved_by_user_id`` is required (Architecture doc SS3.4: every
refund needs a named approver) -- since it's supplied synchronously at
request time, this use case immediately calls ``approve()`` then
``process()`` in the same transaction rather than leaving the refund in
``requested`` for a separate async approval step (disclosed in
``refund.py``'s own docstring).

Posts reversing ``LedgerEntry`` pairs -- the exact mirror image of
``RecordPaymentUseCase``'s own postings: revenue and tax are split
using the same order-subtotal/tax ratio the original payment used (the
Bill/Order are re-resolved from the Payment specifically to reproduce
that split, not assumed), proportional to the refund amount against
the original payment's own amount, so a partial refund reverses only
its own share. Publishes ``RefundProcessed``.
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
from restaurant_os_api.modules.operations.application.dto import RefundDTO, RequestRefundRequestDTO
from restaurant_os_api.modules.operations.application.use_cases._payment_mapper import (
    refund_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import (
    Account,
    LedgerEntry,
    LedgerEntryType,
    Refund,
    RefundStatus,
    TenderType,
)
from restaurant_os_api.modules.operations.domain.events import RefundProcessed
from restaurant_os_api.modules.operations.domain.exceptions import (
    BillNotFoundError,
    PaymentNotFoundError,
    RefundExceedsPaymentError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    BillRepository,
    LedgerRepository,
    OrderRepository,
    PaymentRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "billing.refund"

_TENDER_ACCOUNT = {
    TenderType.CASH: Account.CASH,
    TenderType.CARD: Account.CARD_CLEARING,
    TenderType.WALLET: Account.CARD_CLEARING,
}


class RequestRefundUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        payment_repository_factory: Callable[[AsyncSession], PaymentRepository],
        bill_repository_factory: Callable[[AsyncSession], BillRepository],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        ledger_repository_factory: Callable[[AsyncSession], LedgerRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._payment_repository_factory = payment_repository_factory
        self._bill_repository_factory = bill_repository_factory
        self._order_repository_factory = order_repository_factory
        self._ledger_repository_factory = ledger_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, user_id: str, request: RequestRefundRequestDTO
    ) -> RefundDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            payment_repo = self._payment_repository_factory(uow.session)
            bill_repo = self._bill_repository_factory(uow.session)
            order_repo = self._order_repository_factory(uow.session)
            ledger_repo = self._ledger_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            payment = await payment_repo.get_by_id(tenant_id, request.payment_id)
            if payment is None:
                raise PaymentNotFoundError(request.payment_id)

            bill = await bill_repo.get_by_id(tenant_id, payment.bill_id)
            if bill is None:
                raise BillNotFoundError(payment.bill_id)

            order = await order_repo.get_by_id(tenant_id, bill.order_id) if bill.order_id else None

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=payment.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            existing_refunds = await payment_repo.list_refunds_for_payment(tenant_id, payment.id)
            already_refunded = sum((r.amount for r in existing_refunds), Decimal(0))
            if already_refunded + request.amount > payment.amount:
                raise RefundExceedsPaymentError(payment.id)

            refund = Refund(
                id=generate_ulid(),
                tenant_id=tenant_id,
                branch_id=payment.branch_id,
                payment_id=payment.id,
                order_id=order.id if order is not None else bill.id,
                approved_by_user_id=request.approved_by_user_id,
                amount=request.amount,
                status=RefundStatus.REQUESTED,
                created_at=now,
            )
            refund.approve()
            refund.process()
            refund = await payment_repo.create_refund(refund)

            # Reversing ledger postings -- the same subtotal/tax ratio
            # RecordPaymentUseCase used to split the original payment,
            # reproduced here from the order rather than assumed, then
            # applied proportionally to this refund's share.
            share = request.amount / payment.amount if payment.amount > 0 else Decimal(0)
            non_tip_amount = payment.amount - payment.tip_amount
            this_refund_non_tip = non_tip_amount * share
            tip_reversed = (payment.tip_amount * share).quantize(Decimal("0.0001"))

            subtotal = order.subtotal_amount if order is not None else Decimal(0)
            tax = order.tax_amount if order is not None else Decimal(0)
            revenue_tax_basis = subtotal + tax
            if revenue_tax_basis > 0:
                tax_reversed = (this_refund_non_tip * tax / revenue_tax_basis).quantize(
                    Decimal("0.0001")
                )
            else:
                tax_reversed = Decimal(0)
            revenue_reversed = (this_refund_non_tip - tax_reversed).quantize(Decimal("0.0001"))

            tender_account = _TENDER_ACCOUNT[payment.tender_type]
            await ledger_repo.add(
                LedgerEntry(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    entry_type=LedgerEntryType.CREDIT,
                    account_code=tender_account.value,
                    amount=request.amount,
                    currency_code=payment.currency_code,
                    created_at=now,
                    reference_type="refund",
                    reference_id=refund.id,
                )
            )
            if revenue_reversed > 0:
                await ledger_repo.add(
                    LedgerEntry(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        entry_type=LedgerEntryType.DEBIT,
                        account_code=Account.SALES_REVENUE.value,
                        amount=revenue_reversed,
                        currency_code=payment.currency_code,
                        created_at=now,
                        reference_type="refund",
                        reference_id=refund.id,
                    )
                )
            if tax_reversed > 0:
                await ledger_repo.add(
                    LedgerEntry(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        entry_type=LedgerEntryType.DEBIT,
                        account_code=Account.SALES_TAX_PAYABLE.value,
                        amount=tax_reversed,
                        currency_code=payment.currency_code,
                        created_at=now,
                        reference_type="refund",
                        reference_id=refund.id,
                    )
                )
            if tip_reversed > 0:
                await ledger_repo.add(
                    LedgerEntry(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        entry_type=LedgerEntryType.DEBIT,
                        account_code=Account.TIPS_PAYABLE.value,
                        amount=tip_reversed,
                        currency_code=payment.currency_code,
                        created_at=now,
                        reference_type="refund",
                        reference_id=refund.id,
                    )
                )

            await outbox.publish(
                tenant_id,
                RefundProcessed(
                    refund_id=refund.id,
                    payment_id=payment.id,
                    amount=str(refund.amount),
                    occurred_at=now,
                ),
            )

        return refund_to_dto(refund)
