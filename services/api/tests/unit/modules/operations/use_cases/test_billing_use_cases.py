"""Unit tests for Billing use cases (Sprint 7 Step 4) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.operations.application.dto import (
    ApplyBillAdjustmentRequestDTO,
    GenerateBillRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    ApplyBillAdjustmentUseCase,
    CreateTaxUseCase,
    GenerateBillUseCase,
    GetBillUseCase,
    ListTaxesUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import (
    Bill,
    BillStatus,
    Discount,
    DiscountType,
    Order,
    OrderSource,
    OrderStatus,
    Payment,
    PaymentStatus,
    Tax,
    TenderType,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    AdjustmentApprovalRequiredError,
    BillAlreadyClosedError,
    BillAlreadyExistsError,
    BillNotFoundError,
    ImplausibleTaxRateError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.entities import Branch, BranchStatus
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeResolveUserPermissionsUseCase,
    InMemoryBillRepository,
    InMemoryDiscountRepository,
    InMemoryOrderRepository,
    InMemoryPaymentRepository,
    InMemoryTaxRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import InMemoryBranchRepository

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR01"
BILL_ID = "01ARZ3NDEKTSV4RRFFQ6BILL01"
TAX_ID = "01ARZ3NDEKTSV4RRFFQ6TAX001"
DISCOUNT_ID = "01ARZ3NDEKTSV4RRFFQ6DISC01"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": "restaurant-1",
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _order(**overrides) -> Order:
    defaults = {
        "id": ORDER_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "order_source": OrderSource.POS,
        "status": OrderStatus.FIRED,
        "subtotal_amount": Decimal(100),
        "tax_amount": Decimal(0),
        "currency_code": "USD",
        "opened_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Order(**defaults)


def _bill(**overrides) -> Bill:
    defaults = {
        "id": BILL_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "status": BillStatus.OPEN,
        "created_at": datetime.now(UTC),
        "order_id": ORDER_ID,
    }
    defaults.update(overrides)
    return Bill(**defaults)


def _tax(**overrides) -> Tax:
    defaults = {
        "id": TAX_ID,
        "tenant_id": TENANT_ID,
        "name": "VAT",
        "rate": Decimal("0.1"),
        "is_active": True,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Tax(**defaults)


def _discount(**overrides) -> Discount:
    defaults = {
        "id": DISCOUNT_ID,
        "tenant_id": TENANT_ID,
        "name": "Staff meal",
        "discount_type": DiscountType.PERCENTAGE,
        "value": Decimal(50),
        "requires_approval": False,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Discount(**defaults)


def _payment(**overrides) -> Payment:
    defaults = {
        "id": "01ARZ3NDEKTSV4RRFFQ6PAY001",
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "bill_id": BILL_ID,
        "tender_type": TenderType.CASH,
        "amount": Decimal(50),
        "currency_code": "USD",
        "tip_amount": Decimal(0),
        "status": PaymentStatus.SETTLED,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Payment(**defaults)


class TestCreateTaxUseCase:
    async def test_creates_an_active_tax(self) -> None:
        use_case = CreateTaxUseCase(
            session_factory=_session_factory(),
            tax_repository_factory=lambda _s: InMemoryTaxRepository(),
        )

        tax = await use_case.execute(TENANT_ID, "VAT", "0.1")

        assert tax.name == "VAT"
        assert tax.rate == Decimal("0.1")
        assert tax.is_active is True

    async def test_rejects_a_rate_above_50_percent(self) -> None:
        # Regression test: a tenant's CGST/SGST rows were stored as
        # rate=0.9 (90%) instead of 0.09 (9%) in production -- a
        # legally-shaped fraction under the old 0-1 bound. This check
        # lives in the use case itself (not just the Pydantic schema)
        # so the onboarding entry point, which calls execute() directly
        # with no schema of its own, gets the same guard.
        use_case = CreateTaxUseCase(
            session_factory=_session_factory(),
            tax_repository_factory=lambda _s: InMemoryTaxRepository(),
        )

        with pytest.raises(ImplausibleTaxRateError):
            await use_case.execute(TENANT_ID, "CGST", "0.9")

    async def test_accepts_nine_percent_stored_as_a_fraction(self) -> None:
        use_case = CreateTaxUseCase(
            session_factory=_session_factory(),
            tax_repository_factory=lambda _s: InMemoryTaxRepository(),
        )

        tax = await use_case.execute(TENANT_ID, "CGST", "0.09")

        assert tax.rate == Decimal("0.09")


class TestListTaxesUseCase:
    async def test_lists_only_active_taxes_for_the_tenant(self) -> None:
        active = Tax(
            id="01ARZ3NDEKTSV4RRFFQ6TAX002",
            tenant_id=TENANT_ID,
            name="VAT",
            rate=Decimal("0.1"),
            is_active=True,
            created_at=datetime.now(UTC),
        )
        inactive = Tax(
            id="01ARZ3NDEKTSV4RRFFQ6TAX003",
            tenant_id=TENANT_ID,
            name="Old Tax",
            rate=Decimal("0.05"),
            is_active=False,
            created_at=datetime.now(UTC),
        )
        use_case = ListTaxesUseCase(
            session_factory=_session_factory(),
            tax_repository_factory=lambda _s: InMemoryTaxRepository(
                {active.id: active, inactive.id: inactive}
            ),
        )

        taxes = await use_case.execute(TENANT_ID)

        assert [t.id for t in taxes] == [active.id]


class TestGenerateBillUseCase:
    def _use_case(
        self, order_repo, bill_repo, tax_repo, branch_repo, resolved
    ) -> GenerateBillUseCase:
        return GenerateBillUseCase(
            session_factory=_session_factory(),
            order_repository_factory=lambda _s: order_repo,
            bill_repository_factory=lambda _s: bill_repo,
            tax_repository_factory=lambda _s: tax_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_creates_bill_and_applies_active_taxes_to_the_order(self) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()})
        use_case = self._use_case(
            order_repo,
            InMemoryBillRepository(),
            InMemoryTaxRepository({TAX_ID: _tax()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID, "user-1", GenerateBillRequestDTO(order_id=ORDER_ID)
        )

        assert result.subtotal_amount == Decimal(100)
        assert result.tax_amount == Decimal("10.0")
        assert len(result.tax_lines) == 1
        updated_order = await order_repo.get_by_id(TENANT_ID, ORDER_ID)
        assert updated_order is not None
        assert updated_order.status == OrderStatus.BILLED

    async def test_applies_two_simultaneous_active_taxes_eg_cgst_and_sgst(self) -> None:
        # Indian GST-style setup: two active taxes at once (CGST + SGST,
        # 2.5% each) must both post as separate tax lines against the
        # same order, not just the single-tax case above.
        cgst_id = "01ARZ3NDEKTSV4RRFFQ6TAXCG1"
        sgst_id = "01ARZ3NDEKTSV4RRFFQ6TAXSG1"
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()})
        use_case = self._use_case(
            order_repo,
            InMemoryBillRepository(),
            InMemoryTaxRepository(
                {
                    cgst_id: _tax(id=cgst_id, name="CGST", rate=Decimal("0.025")),
                    sgst_id: _tax(id=sgst_id, name="SGST", rate=Decimal("0.025")),
                }
            ),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID, "user-1", GenerateBillRequestDTO(order_id=ORDER_ID)
        )

        assert result.subtotal_amount == Decimal(100)
        assert result.tax_amount == Decimal("5.0")
        assert len(result.tax_lines) == 2
        tax_ids = {line.tax_id for line in result.tax_lines}
        assert tax_ids == {cgst_id, sgst_id}
        assert all(line.tax_amount == Decimal("2.5") for line in result.tax_lines)

    async def test_nine_percent_cgst_and_sgst_on_3360_is_exact_to_the_paisa(self) -> None:
        # Regression test for a production incident: a tenant's CGST/SGST
        # rows were stored as 0.9 (90%) instead of 0.09 (9%) -- a bad
        # stored value, not a calculation bug (subtotal * rate is and was
        # always correct for a correctly-stored fraction). This pins the
        # exact numbers from that incident report with a properly-stored
        # rate, to the paisa: 3360 * 0.09 = 302.40 per line, 604.80 total
        # tax, 3964.80 due.
        cgst_id = "01ARZ3NDEKTSV4RRFFQ6TAXCG2"
        sgst_id = "01ARZ3NDEKTSV4RRFFQ6TAXSG2"
        order_repo = InMemoryOrderRepository({ORDER_ID: _order(subtotal_amount=Decimal(3360))})
        use_case = self._use_case(
            order_repo,
            InMemoryBillRepository(),
            InMemoryTaxRepository(
                {
                    cgst_id: _tax(id=cgst_id, name="CGST", rate=Decimal("0.09")),
                    sgst_id: _tax(id=sgst_id, name="SGST", rate=Decimal("0.09")),
                }
            ),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID, "user-1", GenerateBillRequestDTO(order_id=ORDER_ID)
        )

        assert result.subtotal_amount == Decimal(3360)
        assert all(line.tax_amount == Decimal("302.40") for line in result.tax_lines)
        assert result.tax_amount == Decimal("604.80")
        assert result.amount_due == Decimal("3964.80")

    async def test_raises_not_found_for_an_unknown_order(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository(),
            InMemoryBillRepository(),
            InMemoryTaxRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", GenerateBillRequestDTO(order_id=ORDER_ID))

    async def test_raises_already_exists_when_the_order_already_has_a_bill(self) -> None:
        use_case = self._use_case(
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBillRepository({BILL_ID: _bill()}),
            InMemoryTaxRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        with pytest.raises(BillAlreadyExistsError):
            await use_case.execute(TENANT_ID, "user-1", GenerateBillRequestDTO(order_id=ORDER_ID))


class TestGetBillUseCase:
    def _use_case(
        self, bill_repo, order_repo, payment_repo, branch_repo, resolved
    ) -> GetBillUseCase:
        return GetBillUseCase(
            session_factory=_session_factory(),
            bill_repository_factory=lambda _s: bill_repo,
            order_repository_factory=lambda _s: order_repo,
            payment_repository_factory=lambda _s: payment_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_returns_the_bill_with_amount_paid_computed_from_settled_payments(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: _bill()}),
            InMemoryOrderRepository({ORDER_ID: _order(tax_amount=Decimal(10))}),
            InMemoryPaymentRepository(
                {
                    "p1": _payment(status=PaymentStatus.SETTLED, amount=Decimal(50)),
                    "p2": _payment(
                        id="01ARZ3NDEKTSV4RRFFQ6PAY002",
                        status=PaymentStatus.AUTHORIZED,
                        amount=Decimal(60),
                    ),
                }
            ),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.read"})),
        )

        result = await use_case.execute(TENANT_ID, "user-1", BILL_ID)

        assert result.id == BILL_ID
        assert result.amount_paid == Decimal(50)
        assert result.subtotal_amount == Decimal(100)
        assert result.tax_amount == Decimal(10)
        # amount_due must reflect the remaining balance, not the bill's
        # original total -- regression lock for the bug where a partial
        # payment never reduced amount_due (110 total - 50 paid = 60).
        assert result.amount_due == Decimal(60)

    async def test_raises_not_found_for_an_unknown_bill(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository(),
            InMemoryOrderRepository(),
            InMemoryPaymentRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.read"})),
        )

        with pytest.raises(BillNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", BILL_ID)


class TestApplyBillAdjustmentUseCase:
    def _use_case(
        self, bill_repo, order_repo, discount_repo, payment_repo, branch_repo, resolved
    ) -> ApplyBillAdjustmentUseCase:
        return ApplyBillAdjustmentUseCase(
            session_factory=_session_factory(),
            bill_repository_factory=lambda _s: bill_repo,
            order_repository_factory=lambda _s: order_repo,
            discount_repository_factory=lambda _s: discount_repo,
            payment_repository_factory=lambda _s: payment_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_signs_a_discount_adjustment_negative_regardless_of_input_sign(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: _bill()}),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryDiscountRepository(),
            InMemoryPaymentRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ApplyBillAdjustmentRequestDTO(
                bill_id=BILL_ID, adjustment_type="discount", amount=Decimal(5)
            ),
        )

        assert len(result.adjustments) == 1
        assert result.adjustments[0].amount == Decimal(-5)
        assert result.adjustments_total == Decimal(-5)

    async def test_computes_amount_from_a_discount_when_discount_id_is_supplied(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: _bill()}),
            InMemoryOrderRepository({ORDER_ID: _order(subtotal_amount=Decimal(100))}),
            InMemoryDiscountRepository({DISCOUNT_ID: _discount(value=Decimal(50))}),
            InMemoryPaymentRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ApplyBillAdjustmentRequestDTO(
                bill_id=BILL_ID, adjustment_type="discount", discount_id=DISCOUNT_ID
            ),
        )

        assert result.adjustments[0].amount == Decimal(-50)

    async def test_raises_approval_required_for_a_flagged_discount_without_an_approver(
        self,
    ) -> None:
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: _bill()}),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryDiscountRepository({DISCOUNT_ID: _discount(requires_approval=True)}),
            InMemoryPaymentRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        with pytest.raises(AdjustmentApprovalRequiredError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ApplyBillAdjustmentRequestDTO(
                    bill_id=BILL_ID, adjustment_type="discount", discount_id=DISCOUNT_ID
                ),
            )

    async def test_raises_already_closed_for_a_closed_bill(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: _bill(status=BillStatus.CLOSED)}),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryDiscountRepository(),
            InMemoryPaymentRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        with pytest.raises(BillAlreadyClosedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ApplyBillAdjustmentRequestDTO(
                    bill_id=BILL_ID, adjustment_type="discount", amount=Decimal(5)
                ),
            )

    async def test_raises_not_found_for_an_unknown_bill(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository(),
            InMemoryOrderRepository(),
            InMemoryDiscountRepository(),
            InMemoryPaymentRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        with pytest.raises(BillNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ApplyBillAdjustmentRequestDTO(
                    bill_id=BILL_ID, adjustment_type="discount", amount=Decimal(5)
                ),
            )
