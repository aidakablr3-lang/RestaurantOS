"""GenerateBillUseCase.

``POST /api/v1/orders/{id}/bill`` -- flat, same coarse/fine
authorization split as ``FireOrderUseCase``. Only legal once the order
has been fired (nothing to bill from ``open``) and has no existing
bill (one Order gets at most one Bill).

Applies every active ``Tax`` configured for the tenant to the order's
``subtotal_amount``, writing one ``OrderTaxLine`` per tax (Data
Architecture v2.0 Group C) and summing them into ``Order.tax_amount``
(previously ``0`` since Step 3 never populated it). Transitions the
order to ``billed`` via ``Order.mark_billed()``.

Tab-based bills (``Bill.tab_id`` set instead of ``order_id``) are not
built by this use case -- a Tab can aggregate several Orders, and
computing one combined tax/adjustment basis across all of them is real,
separate scope. Disclosed, not silently half-supported: this step's
``GenerateBillUseCase`` only ever creates order-scoped bills.

Invoice numbering: only allocated when the branch has a ``gstin`` on
file -- an invoice number implies a real GST registration, and
fabricating one for a branch that isn't (yet, or ever) registered
would misrepresent a registration that doesn't exist. When it applies,
the number is ``"{branch.invoice_prefix}/{financial_year}/{seq:06d}"``,
where ``financial_year`` is computed in IST (not UTC -- see
``platform.financial_year``) and ``seq`` comes from
``InvoiceNumberCounterRepository.allocate_next()``, a single atomic DB
statement in the *same transaction* as this Bill's own insert -- if
anything in this use case fails after the counter increments, the
whole transaction (counter included) rolls back together, so a failed
attempt never burns a number or leaves a gap in the series.
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
from restaurant_os_api.modules.operations.application.dto import BillDTO, GenerateBillRequestDTO
from restaurant_os_api.modules.operations.application.use_cases._bill_mapper import bill_to_dto
from restaurant_os_api.modules.operations.domain.entities import Bill, BillStatus, OrderTaxLine
from restaurant_os_api.modules.operations.domain.exceptions import (
    BillAlreadyExistsError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    BillRepository,
    InvoiceNumberCounterRepository,
    OrderRepository,
    TaxRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.financial_year import indian_financial_year
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "billing.manage"


class GenerateBillUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        bill_repository_factory: Callable[[AsyncSession], BillRepository],
        tax_repository_factory: Callable[[AsyncSession], TaxRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        invoice_number_counter_repository_factory: Callable[
            [AsyncSession], InvoiceNumberCounterRepository
        ],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory
        self._bill_repository_factory = bill_repository_factory
        self._tax_repository_factory = tax_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._invoice_number_counter_repository_factory = invoice_number_counter_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, request: GenerateBillRequestDTO
    ) -> BillDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            bill_repo = self._bill_repository_factory(uow.session)
            tax_repo = self._tax_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            invoice_counter_repo = self._invoice_number_counter_repository_factory(uow.session)

            order = await order_repo.get_by_id(tenant_id, request.order_id)
            if order is None:
                raise OrderNotFoundError(request.order_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            branch = await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=order.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            existing = await bill_repo.get_by_order_id(tenant_id, order.id)
            if existing is not None:
                raise BillAlreadyExistsError(order.id, None)

            taxes = await tax_repo.list_active_for_tenant(tenant_id)
            total_tax = Decimal(0)
            for tax in taxes:
                tax_amount = order.subtotal_amount * tax.rate
                await bill_repo.add_tax_line(
                    OrderTaxLine(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        order_id=order.id,
                        tax_id=tax.id,
                        taxable_amount=order.subtotal_amount,
                        tax_rate_snapshot=tax.rate,
                        tax_amount=tax_amount,
                        created_at=now,
                    )
                )
                total_tax += tax_amount

            order.tax_amount = total_tax
            order.mark_billed()
            order = await order_repo.update(order)

            invoice_number = None
            if branch.gstin is not None:
                financial_year = indian_financial_year(now)
                seq = await invoice_counter_repo.allocate_next(tenant_id, branch.id, financial_year)
                invoice_number = f"{branch.invoice_prefix}/{financial_year}/{seq:06d}"

            bill = await bill_repo.create(
                Bill(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=order.branch_id,
                    status=BillStatus.OPEN,
                    created_at=now,
                    order_id=order.id,
                    invoice_number=invoice_number,
                )
            )

            tax_lines = await bill_repo.get_tax_lines_for_order(tenant_id, order.id)

        return bill_to_dto(
            bill,
            subtotal_amount=order.subtotal_amount,
            tax_amount=order.tax_amount,
            tax_lines=tax_lines,
            adjustments=[],
            amount_paid=Decimal(0),
        )
