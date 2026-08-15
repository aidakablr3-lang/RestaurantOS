"""Unit tests for Payment/Refund use cases (Sprint 7 Step 4) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.operations.application.dto import (
    RecordPaymentRequestDTO,
    RequestRefundRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    ListPaymentsUseCase,
    RecordPaymentUseCase,
    RequestRefundUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import (
    Bill,
    BillStatus,
    Order,
    OrderSource,
    OrderStatus,
    Payment,
    PaymentStatus,
    TenderType,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    BillAlreadyClosedError,
    BillNotFoundError,
    OverpaymentError,
    PaymentNotFoundError,
    RefundExceedsPaymentError,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    Restaurant,
    RestaurantStatus,
    Table,
    TableStatus,
)
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    FakeResolveUserPermissionsUseCase,
    InMemoryBillRepository,
    InMemoryLedgerRepository,
    InMemoryOrderRepository,
    InMemoryPaymentRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import (
    InMemoryBranchRepository,
    InMemoryRestaurantRepository,
    InMemoryTableRepository,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR01"
ORDER2_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR02"
BILL_ID = "01ARZ3NDEKTSV4RRFFQ6BILL01"
BILL2_ID = "01ARZ3NDEKTSV4RRFFQ6BILL02"
PAYMENT_ID = "01ARZ3NDEKTSV4RRFFQ6PAY001"
TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABL01"


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
        "status": OrderStatus.BILLED,
        "subtotal_amount": Decimal(100),
        "tax_amount": Decimal(10),
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


def _restaurant(**overrides) -> Restaurant:
    defaults = {
        "id": "restaurant-1",
        "tenant_id": TENANT_ID,
        "legal_name": "R",
        "display_name": "R",
        "default_currency_code": "USD",
        "status": RestaurantStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Restaurant(**defaults)


def _table(**overrides) -> Table:
    defaults = {
        "id": TABLE_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "table_zone_id": "01ARZ3NDEKTSV4RRFFQ6ZONE01",
        "table_number": "5",
        "capacity": 4,
        "status": TableStatus.OCCUPIED,
        "sync_version": 1,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Table(**defaults)


def _payment(**overrides) -> Payment:
    defaults = {
        "id": PAYMENT_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "bill_id": BILL_ID,
        "tender_type": TenderType.CASH,
        "amount": Decimal(110),
        "currency_code": "USD",
        "tip_amount": Decimal(0),
        "status": PaymentStatus.SETTLED,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Payment(**defaults)


class TestRecordPaymentUseCase:
    def _use_case(
        self,
        bill_repo,
        order_repo,
        payment_repo,
        ledger_repo,
        branch_repo,
        resolved,
        outbox,
        table_repo=None,
        restaurant_repo=None,
    ) -> RecordPaymentUseCase:
        return RecordPaymentUseCase(
            session_factory=_session_factory(),
            bill_repository_factory=lambda _s: bill_repo,
            order_repository_factory=lambda _s: order_repo,
            payment_repository_factory=lambda _s: payment_repo,
            ledger_repository_factory=lambda _s: ledger_repo,
            branch_repository_factory=lambda _s: branch_repo,
            table_repository_factory=lambda _s: table_repo or InMemoryTableRepository(),
            restaurant_repository_factory=lambda _s: (
                restaurant_repo or InMemoryRestaurantRepository({"restaurant-1": _restaurant()})
            ),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_settling_the_full_amount_closes_the_bill_and_order_and_posts_the_ledger(
        self,
    ) -> None:
        bill_repo = InMemoryBillRepository({BILL_ID: _bill()})
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()})
        ledger_repo = InMemoryLedgerRepository()
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            bill_repo,
            order_repo,
            InMemoryPaymentRepository(),
            ledger_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(110)),
        )

        assert result.status == "settled"
        assert result.tip_amount == Decimal(0)
        updated_bill = await bill_repo.get_by_id(TENANT_ID, BILL_ID)
        assert updated_bill is not None
        assert updated_bill.status == BillStatus.CLOSED
        updated_order = await order_repo.get_by_id(TENANT_ID, ORDER_ID)
        assert updated_order is not None
        assert updated_order.status == OrderStatus.CLOSED
        entries, total = await ledger_repo.list_for_tenant(TENANT_ID, offset=0, limit=10)
        assert total == 3
        assert sum(1 for e in entries if e.entry_type.value == "debit") == 1
        assert sum(1 for e in entries if e.entry_type.value == "credit") == 2
        assert len(outbox.published) == 1

    async def test_a_partial_payment_leaves_the_bill_and_order_open(self) -> None:
        bill_repo = InMemoryBillRepository({BILL_ID: _bill()})
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()})
        use_case = self._use_case(
            bill_repo,
            order_repo,
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(50)),
        )

        updated_bill = await bill_repo.get_by_id(TENANT_ID, BILL_ID)
        assert updated_bill is not None
        assert updated_bill.status == BillStatus.PARTIALLY_PAID
        updated_order = await order_repo.get_by_id(TENANT_ID, ORDER_ID)
        assert updated_order is not None
        assert updated_order.status == OrderStatus.BILLED

    async def test_full_payment_releases_an_occupied_table(self) -> None:
        bill_repo = InMemoryBillRepository({BILL_ID: _bill()})
        order_repo = InMemoryOrderRepository({ORDER_ID: _order(table_id=TABLE_ID)})
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = self._use_case(
            bill_repo,
            order_repo,
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
            table_repo=table_repo,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(110)),
        )

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.AVAILABLE

    async def test_partial_payment_leaves_the_table_occupied(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: _bill()}),
            InMemoryOrderRepository({ORDER_ID: _order(table_id=TABLE_ID)}),
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
            table_repo=table_repo,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(50)),
        )

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.OCCUPIED

    async def test_settling_one_of_two_orders_on_the_table_leaves_it_occupied(self) -> None:
        # Defect #1 remediation: a second, still-active order against the
        # same table must keep it occupied even after the first order's
        # bill is fully paid and closed.
        bill_repo = InMemoryBillRepository({BILL_ID: _bill()})
        order_repo = InMemoryOrderRepository(
            {
                ORDER_ID: _order(table_id=TABLE_ID),
                ORDER2_ID: _order(id=ORDER2_ID, table_id=TABLE_ID, status=OrderStatus.FIRED),
            }
        )
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = self._use_case(
            bill_repo,
            order_repo,
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
            table_repo=table_repo,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(110)),
        )

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.OCCUPIED
        updated_order = await order_repo.get_by_id(TENANT_ID, ORDER_ID)
        assert updated_order is not None
        assert updated_order.status == OrderStatus.CLOSED

    async def test_settling_the_last_active_order_on_the_table_releases_it(self) -> None:
        # Same setup as above, but the sibling order was already settled
        # earlier -- this payment is for the table's last remaining
        # active order, so only now should the table become available.
        bill_repo = InMemoryBillRepository({BILL2_ID: _bill(id=BILL2_ID, order_id=ORDER2_ID)})
        order_repo = InMemoryOrderRepository(
            {
                ORDER_ID: _order(table_id=TABLE_ID, status=OrderStatus.CLOSED),
                ORDER2_ID: _order(id=ORDER2_ID, table_id=TABLE_ID),
            }
        )
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = self._use_case(
            bill_repo,
            order_repo,
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
            table_repo=table_repo,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordPaymentRequestDTO(bill_id=BILL2_ID, tender_type="cash", amount=Decimal(110)),
        )

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.AVAILABLE

    async def test_a_voided_sibling_order_does_not_block_release(self) -> None:
        # A voided order on the same table must not count as "active" --
        # it should not prevent the table from being released.
        bill_repo = InMemoryBillRepository({BILL_ID: _bill()})
        order_repo = InMemoryOrderRepository(
            {
                ORDER_ID: _order(table_id=TABLE_ID),
                ORDER2_ID: _order(id=ORDER2_ID, table_id=TABLE_ID, status=OrderStatus.VOIDED),
            }
        )
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = self._use_case(
            bill_repo,
            order_repo,
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
            table_repo=table_repo,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(110)),
        )

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.AVAILABLE

    async def test_an_active_order_on_a_different_table_does_not_block_release(self) -> None:
        other_table_id = "01ARZ3NDEKTSV4RRFFQ6TABL02"
        bill_repo = InMemoryBillRepository({BILL_ID: _bill()})
        order_repo = InMemoryOrderRepository(
            {
                ORDER_ID: _order(table_id=TABLE_ID),
                ORDER2_ID: _order(id=ORDER2_ID, table_id=other_table_id, status=OrderStatus.FIRED),
            }
        )
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = self._use_case(
            bill_repo,
            order_repo,
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
            table_repo=table_repo,
        )

        await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(110)),
        )

        table = await table_repo.get_by_id(TENANT_ID, TABLE_ID)
        assert table is not None
        assert table.status == TableStatus.AVAILABLE

    async def test_a_tab_based_payment_resolves_currency_from_the_restaurant(self) -> None:
        # Tab-based bills carry no order_id, so there's no Order to read
        # currency_code from -- this must resolve from the branch's own
        # Restaurant instead of falling back to a hardcoded "USD".
        tab_bill = _bill(order_id=None, tab_id="tab-1")
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: tab_bill}),
            InMemoryOrderRepository(),
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
            restaurant_repo=InMemoryRestaurantRepository(
                {"restaurant-1": _restaurant(default_currency_code="INR")}
            ),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(0)),
        )

        assert result.currency_code == "INR"

    async def test_raises_overpayment_when_amount_exceeds_amount_due(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: _bill()}),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(OverpaymentError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(200)),
            )

    async def test_raises_already_closed_for_a_closed_bill(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: _bill(status=BillStatus.CLOSED)}),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(BillAlreadyClosedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(10)),
            )

    async def test_raises_not_found_for_an_unknown_bill(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository(),
            InMemoryOrderRepository(),
            InMemoryPaymentRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(BillNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                RecordPaymentRequestDTO(bill_id=BILL_ID, tender_type="cash", amount=Decimal(10)),
            )


class TestListPaymentsUseCase:
    def _use_case(self, bill_repo, payment_repo, branch_repo, resolved) -> ListPaymentsUseCase:
        return ListPaymentsUseCase(
            session_factory=_session_factory(),
            bill_repository_factory=lambda _s: bill_repo,
            payment_repository_factory=lambda _s: payment_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_lists_payments_for_a_bill(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository({BILL_ID: _bill()}),
            InMemoryPaymentRepository({PAYMENT_ID: _payment()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.read"})),
        )

        result = await use_case.execute(TENANT_ID, "user-1", BILL_ID)

        assert len(result) == 1
        assert result[0].id == PAYMENT_ID

    async def test_raises_not_found_for_an_unknown_bill(self) -> None:
        use_case = self._use_case(
            InMemoryBillRepository(),
            InMemoryPaymentRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.read"})),
        )

        with pytest.raises(BillNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", BILL_ID)


class TestRequestRefundUseCase:
    def _use_case(
        self, payment_repo, bill_repo, order_repo, ledger_repo, branch_repo, resolved, outbox
    ) -> RequestRefundUseCase:
        return RequestRefundUseCase(
            session_factory=_session_factory(),
            payment_repository_factory=lambda _s: payment_repo,
            bill_repository_factory=lambda _s: bill_repo,
            order_repository_factory=lambda _s: order_repo,
            ledger_repository_factory=lambda _s: ledger_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_processes_a_partial_refund_and_posts_reversing_ledger_entries(self) -> None:
        ledger_repo = InMemoryLedgerRepository()
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            InMemoryPaymentRepository({PAYMENT_ID: _payment()}),
            InMemoryBillRepository({BILL_ID: _bill(status=BillStatus.CLOSED)}),
            InMemoryOrderRepository({ORDER_ID: _order(status=OrderStatus.CLOSED)}),
            ledger_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.refund"})),
            outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            RequestRefundRequestDTO(
                payment_id=PAYMENT_ID, approved_by_user_id="user-1", amount=Decimal(55)
            ),
        )

        assert result.status == "processed"
        assert result.amount == Decimal(55)
        entries, total = await ledger_repo.list_for_tenant(TENANT_ID, offset=0, limit=10)
        assert total == 3
        assert sum(1 for e in entries if e.entry_type.value == "credit") == 1
        assert sum(1 for e in entries if e.entry_type.value == "debit") == 2
        assert len(outbox.published) == 1

    async def test_raises_exceeds_payment_when_refund_amount_exceeds_the_payment(self) -> None:
        use_case = self._use_case(
            InMemoryPaymentRepository({PAYMENT_ID: _payment()}),
            InMemoryBillRepository({BILL_ID: _bill(status=BillStatus.CLOSED)}),
            InMemoryOrderRepository({ORDER_ID: _order(status=OrderStatus.CLOSED)}),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.refund"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(RefundExceedsPaymentError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                RequestRefundRequestDTO(
                    payment_id=PAYMENT_ID, approved_by_user_id="user-1", amount=Decimal(200)
                ),
            )

    async def test_raises_not_found_for_an_unknown_payment(self) -> None:
        use_case = self._use_case(
            InMemoryPaymentRepository(),
            InMemoryBillRepository(),
            InMemoryOrderRepository(),
            InMemoryLedgerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.refund"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(PaymentNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                RequestRefundRequestDTO(
                    payment_id=PAYMENT_ID, approved_by_user_id="user-1", amount=Decimal(10)
                ),
            )
