"""RecordPaymentUseCase.

Flat ``POST /api/v1/bills/{id}/payments``. No real payment gateway
exists (Architecture doc SS2.1's disclosed scope cut), so a payment is
driven straight through ``authorized -> captured -> settled``
synchronously in one call.

**Business rule (P0 correction, 2026-08-12): a tip is not part of the
restaurant bill.** The customer owes exactly food/drinks + tax +
adjustments -- nothing else. A payment's ``amount`` is applied to the
bill in full; no tip value is read from the request or subtracted from
it anywhere in this calculation. ``Payment.tip_amount`` still exists on
the entity/schema for backward compatibility with any historical rows,
but every payment recorded through this use case now always persists
``tip_amount=0`` -- the API no longer accepts a client-supplied tip
(see ``RecordPaymentRequestSchema``). Tipping, if it happens at all, is
a transaction between the guest and the server that happens entirely
outside RestaurantOS.

**Overpayment guard:** compares the sum of every prior settled
payment's amount, plus this payment's own amount, against the bill's
``amount_due`` (order subtotal + tax + adjustments). A payment equal to
``amount_due`` closes the bill; a payment greater than the remaining
``amount_due`` is rejected. The bill row is locked (``SELECT ... FOR
UPDATE``, via ``get_by_id_for_update``) for the duration of this
read-guard-write sequence, so two concurrent payments against the same
bill serialize rather than both reading the same pre-payment
``amount_paid`` and both passing the guard (P0 defect found in Phase
2.3, fixed 2026-08-14).

**Ledger posting (Data Architecture v2.0 Group I):** one debit against
``CASH``/``CARD_CLEARING`` (by ``tender_type``) for the full payment
amount, matched by credits to ``SALES_REVENUE`` and
``SALES_TAX_PAYABLE`` -- split proportionally from the order's own
subtotal/tax ratio. **Disclosed limitation:** this proportional split
uses the *order's* totals, not a Tab's combined total across multiple
orders -- correct for the common single-order-bill path this step's
own tests exercise; Tab-based bills (out of scope for
``GenerateBillUseCase`` too, see that file) would need this revisited.

Once the bill's ``amount_paid`` reaches ``amount_due``, the bill closes
and the underlying Order closes with it (``Order.close()``), and --
the other half of this same P0 correction -- a dine-in order's table is
released back to ``available`` in the same transaction (via the shared
``release_table_if_occupied`` helper ``CloseOrderUseCase``/
``VoidOrderUseCase`` already use), so a fully-paid table never gets
stuck ``occupied`` waiting on a separate manual step. "Closing out a
table" in real POS terms. Publishes ``PaymentSettled``.
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
    PaymentDTO,
    RecordPaymentRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._payment_mapper import (
    payment_to_dto,
)
from restaurant_os_api.modules.operations.application.use_cases._table_release import (
    release_table_if_occupied,
)
from restaurant_os_api.modules.operations.domain.entities import (
    Account,
    LedgerEntry,
    LedgerEntryType,
    Payment,
    PaymentStatus,
    TenderType,
)
from restaurant_os_api.modules.operations.domain.events import PaymentSettled
from restaurant_os_api.modules.operations.domain.exceptions import (
    BillAlreadyClosedError,
    BillNotFoundError,
    OrderNotFoundError,
    OverpaymentError,
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
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, TableRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "billing.manage"

_TENDER_ACCOUNT = {
    TenderType.CASH: Account.CASH,
    TenderType.CARD: Account.CARD_CLEARING,
    TenderType.WALLET: Account.CARD_CLEARING,
}


class RecordPaymentUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        bill_repository_factory: Callable[[AsyncSession], BillRepository],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        payment_repository_factory: Callable[[AsyncSession], PaymentRepository],
        ledger_repository_factory: Callable[[AsyncSession], LedgerRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._bill_repository_factory = bill_repository_factory
        self._order_repository_factory = order_repository_factory
        self._payment_repository_factory = payment_repository_factory
        self._ledger_repository_factory = ledger_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._table_repository_factory = table_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, user_id: str, request: RecordPaymentRequestDTO
    ) -> PaymentDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            bill_repo = self._bill_repository_factory(uow.session)
            order_repo = self._order_repository_factory(uow.session)
            payment_repo = self._payment_repository_factory(uow.session)
            ledger_repo = self._ledger_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            # Locked for the rest of this transaction so a concurrent
            # payment against the same bill blocks here instead of
            # reading a stale amount_paid and passing the overpayment
            # guard below alongside this one (P0, Phase 2.3).
            bill = await bill_repo.get_by_id_for_update(tenant_id, request.bill_id)
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

            adjustments = await bill_repo.get_adjustments(tenant_id, bill.id)
            adjustments_total = sum((a.amount for a in adjustments), Decimal(0))
            subtotal = order.subtotal_amount if order is not None else Decimal(0)
            tax = order.tax_amount if order is not None else Decimal(0)
            amount_due = subtotal + tax + adjustments_total

            existing_payments = await payment_repo.list_for_bill(tenant_id, bill.id)
            prior_bill_paid = sum(
                (p.amount for p in existing_payments if p.status == PaymentStatus.SETTLED),
                Decimal(0),
            )
            new_total_paid = prior_bill_paid + request.amount
            if new_total_paid > amount_due:
                raise OverpaymentError(bill.id, str(amount_due), str(new_total_paid))

            payment = Payment(
                id=generate_ulid(),
                tenant_id=tenant_id,
                branch_id=bill.branch_id,
                bill_id=bill.id,
                tender_type=TenderType(request.tender_type),
                amount=request.amount,
                currency_code=order.currency_code if order is not None else "USD",
                tip_amount=Decimal(0),
                status=PaymentStatus.AUTHORIZED,
                created_at=now,
                gateway_token_ref=request.gateway_token_ref,
                gateway_last4=request.gateway_last4,
            )
            payment.capture()
            payment.settle()
            payment = await payment_repo.create(payment)

            # Ledger posting: one debit, matched by credits that sum to
            # the same amount (Data Architecture v2.0 Group I).
            revenue_tax_basis = subtotal + tax
            if revenue_tax_basis > 0:
                tax_share = (request.amount * tax / revenue_tax_basis).quantize(Decimal("0.0001"))
            else:
                tax_share = Decimal(0)
            revenue_share = request.amount - tax_share

            tender_account = _TENDER_ACCOUNT[payment.tender_type]
            await ledger_repo.add(
                LedgerEntry(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    entry_type=LedgerEntryType.DEBIT,
                    account_code=tender_account.value,
                    amount=payment.amount,
                    currency_code=payment.currency_code,
                    created_at=now,
                    reference_type="payment",
                    reference_id=payment.id,
                )
            )
            if revenue_share > 0:
                await ledger_repo.add(
                    LedgerEntry(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        entry_type=LedgerEntryType.CREDIT,
                        account_code=Account.SALES_REVENUE.value,
                        amount=revenue_share,
                        currency_code=payment.currency_code,
                        created_at=now,
                        reference_type="payment",
                        reference_id=payment.id,
                    )
                )
            if tax_share > 0:
                await ledger_repo.add(
                    LedgerEntry(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        entry_type=LedgerEntryType.CREDIT,
                        account_code=Account.SALES_TAX_PAYABLE.value,
                        amount=tax_share,
                        currency_code=payment.currency_code,
                        created_at=now,
                        reference_type="payment",
                        reference_id=payment.id,
                    )
                )

            fully_paid = new_total_paid >= amount_due
            bill.apply_payment_status(fully_paid=fully_paid)
            bill = await bill_repo.update(bill)

            if fully_paid and order is not None:
                order.close(closed_at=now)
                await order_repo.update(order)
                if order.table_id is not None:
                    await release_table_if_occupied(
                        table_repo, order_repo, tenant_id, order.table_id
                    )

            await outbox.publish(
                tenant_id,
                PaymentSettled(
                    payment_id=payment.id,
                    bill_id=bill.id,
                    amount=str(payment.amount),
                    occurred_at=now,
                ),
            )

        return payment_to_dto(payment)
