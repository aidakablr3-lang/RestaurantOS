"""Unit tests for GetEndOfDayReportUseCase (full-day operational
simulation gap fix) -- in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.operations.application.use_cases import GetEndOfDayReportUseCase
from restaurant_os_api.modules.operations.domain.entities import (
    Order,
    OrderItem,
    OrderItemLineStatus,
    OrderSource,
    OrderStatus,
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
    TenderType,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    MenuItem,
    Restaurant,
    RestaurantStatus,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    InMemoryOrderRepository,
    InMemoryPaymentRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import (
    InMemoryBranchRepository,
    InMemoryMenuItemRepository,
    InMemoryRestaurantRepository,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT01"
MENU_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6MITM01"
OTHER_MENU_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6MITM02"
ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR01"
VOIDED_ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR02"
OPEN_ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR03"
BILLED_ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR04"
CLOSED_ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR05"
REPORT_DATE = date(2026, 8, 12)
IN_WINDOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
BEFORE_WINDOW = datetime(2026, 8, 11, 23, 0, tzinfo=UTC)
AFTER_WINDOW = datetime(2026, 8, 13, 1, 0, tzinfo=UTC)


def _restaurant(**overrides) -> Restaurant:
    defaults = {
        "id": RESTAURANT_ID,
        "tenant_id": TENANT_ID,
        "legal_name": "Test Restaurant LLC",
        "display_name": "Test Restaurant",
        "default_currency_code": "USD",
        "status": RestaurantStatus.ACTIVE,
        "created_at": IN_WINDOW,
    }
    defaults.update(overrides)
    return Restaurant(**defaults)


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": IN_WINDOW,
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _menu_item(**overrides) -> MenuItem:
    defaults = {
        "id": MENU_ITEM_ID,
        "tenant_id": TENANT_ID,
        "menu_category_id": MENU_CATEGORY_ID,
        "name": "Burger",
        "price_amount": Decimal("8.99"),
        "currency_code": "USD",
        "is_available": True,
        "display_order": 0,
        "created_at": IN_WINDOW,
    }
    defaults.update(overrides)
    return MenuItem(**defaults)


def _order(**overrides) -> Order:
    defaults = {
        "id": ORDER_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "order_source": OrderSource.POS,
        "status": OrderStatus.SERVED,
        "subtotal_amount": Decimal("20.00"),
        "tax_amount": Decimal("2.00"),
        "currency_code": "USD",
        "opened_at": IN_WINDOW,
        "created_at": IN_WINDOW,
    }
    defaults.update(overrides)
    return Order(**defaults)


def _order_item(**overrides) -> OrderItem:
    defaults = {
        "id": "01ARZ3NDEKTSV4RRFFQ6OITM01",
        "tenant_id": TENANT_ID,
        "order_id": ORDER_ID,
        "menu_item_id": MENU_ITEM_ID,
        "quantity": 2,
        "unit_price_amount": Decimal("8.99"),
        "line_status": OrderItemLineStatus.SERVED,
        "created_at": IN_WINDOW,
    }
    defaults.update(overrides)
    return OrderItem(**defaults)


def _payment(**overrides) -> Payment:
    defaults = {
        "id": "01ARZ3NDEKTSV4RRFFQ6PMT001",
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "bill_id": "01ARZ3NDEKTSV4RRFFQ6BILL01",
        "tender_type": TenderType.CASH,
        "amount": Decimal("22.00"),
        "currency_code": "USD",
        "tip_amount": Decimal("3.00"),
        "status": PaymentStatus.SETTLED,
        "created_at": IN_WINDOW,
    }
    defaults.update(overrides)
    return Payment(**defaults)


def _refund(**overrides) -> Refund:
    defaults = {
        "id": "01ARZ3NDEKTSV4RRFFQ6RFND01",
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "payment_id": "01ARZ3NDEKTSV4RRFFQ6PMT001",
        "order_id": ORDER_ID,
        "approved_by_user_id": "user-1",
        "amount": Decimal("5.00"),
        "status": RefundStatus.PROCESSED,
        "created_at": IN_WINDOW,
    }
    defaults.update(overrides)
    return Refund(**defaults)


def _use_case(
    order_repo, payment_repo, *, branch_repo=None, restaurant_repo=None, menu_item_repo=None
):
    return GetEndOfDayReportUseCase(
        session_factory=fake_session_factory_returning(FakeAsyncSession()),
        branch_repository_factory=lambda _s: (
            branch_repo
            if branch_repo is not None
            else InMemoryBranchRepository({BRANCH_ID: _branch()})
        ),
        restaurant_repository_factory=lambda _s: (
            restaurant_repo
            if restaurant_repo is not None
            else InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()})
        ),
        order_repository_factory=lambda _s: order_repo,
        payment_repository_factory=lambda _s: payment_repo,
        menu_item_repository_factory=lambda _s: (
            menu_item_repo
            if menu_item_repo is not None
            else InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        ),
    )


class TestGetEndOfDayReportUseCase:
    async def test_aggregates_sales_items_and_payments_within_the_window(self) -> None:
        order_repo = InMemoryOrderRepository({ORDER_ID: _order()}, {"item-1": _order_item()})
        payment_repo = InMemoryPaymentRepository({"payment-1": _payment()})
        use_case = _use_case(order_repo, payment_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.branch_id == BRANCH_ID
        assert result.report_date == "2026-08-12"
        assert result.currency_code == "USD"
        assert result.order_count == 1
        assert result.items_sold_count == 2
        assert result.gross_sales_amount == Decimal("22.00")
        assert result.total_collected_amount == Decimal("22.00")
        assert result.total_tips_amount == Decimal("3.00")

    async def test_voided_orders_are_excluded_from_gross_sales_but_counted_separately(
        self,
    ) -> None:
        order_repo = InMemoryOrderRepository(
            {
                ORDER_ID: _order(),
                VOIDED_ORDER_ID: _order(
                    id=VOIDED_ORDER_ID,
                    status=OrderStatus.VOIDED,
                    subtotal_amount=Decimal("10.00"),
                    tax_amount=Decimal("1.00"),
                ),
            },
            {"item-1": _order_item()},
        )
        payment_repo = InMemoryPaymentRepository()
        use_case = _use_case(order_repo, payment_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.order_count == 1
        assert result.voided_order_count == 1
        assert result.gross_sales_amount == Decimal("22.00")
        assert result.voided_sales_amount == Decimal("11.00")

    async def test_a_never_served_open_order_does_not_inflate_gross_sales(self) -> None:
        # Defect #2 remediation (Phase 2.1): an order still sitting in
        # OPEN (never fired, never served, no bill raised -- the same
        # bucket a failed/insufficient-stock add-item attempt would leave
        # an order in, since there is no separate "failed" order status
        # in this domain model) is not a realized sale and must not
        # inflate Gross Sales.
        order_repo = InMemoryOrderRepository(
            {
                ORDER_ID: _order(),
                OPEN_ORDER_ID: _order(
                    id=OPEN_ORDER_ID,
                    status=OrderStatus.OPEN,
                    subtotal_amount=Decimal("999.00"),
                    tax_amount=Decimal("99.90"),
                ),
            },
            {"item-1": _order_item()},
        )
        use_case = _use_case(order_repo, InMemoryPaymentRepository())

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.gross_sales_amount == Decimal("22.00")
        assert result.outstanding_amount == Decimal(0)
        # order_count is a traffic metric, not a revenue claim -- the
        # still-open order legitimately counts as a non-voided order.
        assert result.order_count == 2

    async def test_a_billed_but_unpaid_order_counts_toward_gross_sales_and_outstanding(
        self,
    ) -> None:
        order_repo = InMemoryOrderRepository(
            {
                BILLED_ORDER_ID: _order(
                    id=BILLED_ORDER_ID,
                    status=OrderStatus.BILLED,
                    subtotal_amount=Decimal("15.00"),
                    tax_amount=Decimal("1.50"),
                )
            }
        )
        use_case = _use_case(order_repo, InMemoryPaymentRepository())

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.gross_sales_amount == Decimal("16.50")
        assert result.outstanding_amount == Decimal("16.50")
        assert result.total_collected_amount == Decimal(0)

    async def test_a_fully_paid_closed_order_is_not_outstanding(self) -> None:
        order_repo = InMemoryOrderRepository(
            {CLOSED_ORDER_ID: _order(id=CLOSED_ORDER_ID, status=OrderStatus.CLOSED)}
        )
        payment_repo = InMemoryPaymentRepository({"payment-1": _payment()})
        use_case = _use_case(order_repo, payment_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.gross_sales_amount == Decimal("22.00")
        assert result.outstanding_amount == Decimal(0)
        assert result.total_collected_amount == Decimal("22.00")

    async def test_a_partially_paid_billed_order_stays_outstanding(self) -> None:
        # A partial payment does not transition the order out of BILLED
        # (RecordPaymentUseCase only closes it once fully paid), so it
        # must still show up as outstanding, with only the actual
        # partial amount reflected in Total Collected.
        order_repo = InMemoryOrderRepository(
            {
                BILLED_ORDER_ID: _order(
                    id=BILLED_ORDER_ID,
                    status=OrderStatus.BILLED,
                    subtotal_amount=Decimal("20.00"),
                    tax_amount=Decimal("2.00"),
                )
            }
        )
        payment_repo = InMemoryPaymentRepository(
            {"payment-1": _payment(amount=Decimal("10.00"), tip_amount=Decimal(0))}
        )
        use_case = _use_case(order_repo, payment_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.gross_sales_amount == Decimal("22.00")
        assert result.outstanding_amount == Decimal("22.00")
        assert result.total_collected_amount == Decimal("10.00")

    async def test_mixed_order_states_produce_correct_gross_sales_outstanding_and_voided_totals(
        self,
    ) -> None:
        # Combined EOD scenario: one served/paid order, one billed/unpaid
        # order, one never-served open order, and one voided order, all
        # in the same window -- verifies every total against a
        # hand-calculated expected value simultaneously.
        order_repo = InMemoryOrderRepository(
            {
                CLOSED_ORDER_ID: _order(
                    id=CLOSED_ORDER_ID,
                    status=OrderStatus.CLOSED,
                    subtotal_amount=Decimal("20.00"),
                    tax_amount=Decimal("2.00"),
                ),
                BILLED_ORDER_ID: _order(
                    id=BILLED_ORDER_ID,
                    status=OrderStatus.BILLED,
                    subtotal_amount=Decimal("15.00"),
                    tax_amount=Decimal("1.50"),
                ),
                OPEN_ORDER_ID: _order(
                    id=OPEN_ORDER_ID,
                    status=OrderStatus.OPEN,
                    subtotal_amount=Decimal("50.00"),
                    tax_amount=Decimal("5.00"),
                ),
                VOIDED_ORDER_ID: _order(
                    id=VOIDED_ORDER_ID,
                    status=OrderStatus.VOIDED,
                    subtotal_amount=Decimal("10.00"),
                    tax_amount=Decimal("1.00"),
                ),
            }
        )
        payment_repo = InMemoryPaymentRepository(
            {"payment-1": _payment(amount=Decimal("22.00"), tip_amount=Decimal("3.00"))}
        )
        use_case = _use_case(order_repo, payment_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.order_count == 3  # CLOSED + BILLED + OPEN, non-voided
        assert result.voided_order_count == 1
        assert result.gross_sales_amount == Decimal("38.50")  # 22.00 (closed) + 16.50 (billed)
        assert result.outstanding_amount == Decimal("16.50")  # billed only
        assert result.voided_sales_amount == Decimal("11.00")
        assert result.total_collected_amount == Decimal("22.00")

    async def test_voided_line_items_do_not_count_toward_items_sold(self) -> None:
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order()},
            {
                "item-1": _order_item(),
                "item-2": _order_item(
                    id="01ARZ3NDEKTSV4RRFFQ6OITM02", line_status=OrderItemLineStatus.VOIDED
                ),
            },
        )
        use_case = _use_case(order_repo, InMemoryPaymentRepository())

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.items_sold_count == 2

    async def test_orders_outside_the_date_window_are_excluded(self) -> None:
        order_repo = InMemoryOrderRepository(
            {
                ORDER_ID: _order(opened_at=BEFORE_WINDOW),
                VOIDED_ORDER_ID: _order(id=VOIDED_ORDER_ID, opened_at=AFTER_WINDOW),
            }
        )
        use_case = _use_case(order_repo, InMemoryPaymentRepository())

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.order_count == 0
        assert result.voided_order_count == 0

    async def test_refunds_reduce_net_collected_but_not_gross_collected(self) -> None:
        payment_repo = InMemoryPaymentRepository({"payment-1": _payment()}, {"refund-1": _refund()})
        use_case = _use_case(InMemoryOrderRepository(), payment_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.total_collected_amount == Decimal("22.00")
        assert result.total_refunded_amount == Decimal("5.00")
        assert result.net_collected_amount == Decimal("17.00")

    async def test_tender_breakdown_groups_by_tender_type(self) -> None:
        payment_repo = InMemoryPaymentRepository(
            {
                "payment-1": _payment(tender_type=TenderType.CASH, amount=Decimal("10.00")),
                "payment-2": _payment(
                    id="01ARZ3NDEKTSV4RRFFQ6PMT002",
                    tender_type=TenderType.CARD,
                    amount=Decimal("15.00"),
                ),
                "payment-3": _payment(
                    id="01ARZ3NDEKTSV4RRFFQ6PMT003",
                    tender_type=TenderType.CARD,
                    amount=Decimal("5.00"),
                ),
            }
        )
        use_case = _use_case(InMemoryOrderRepository(), payment_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        breakdown = {t.tender_type: (t.amount, t.payment_count) for t in result.tender_breakdown}
        assert breakdown["cash"] == (Decimal("10.00"), 1)
        assert breakdown["card"] == (Decimal("20.00"), 2)

    async def test_top_items_are_sorted_by_quantity_sold_descending_with_resolved_names(
        self,
    ) -> None:
        order_repo = InMemoryOrderRepository(
            {ORDER_ID: _order()},
            {
                "item-1": _order_item(menu_item_id=MENU_ITEM_ID, quantity=2),
                "item-2": _order_item(
                    id="01ARZ3NDEKTSV4RRFFQ6OITM02",
                    menu_item_id=OTHER_MENU_ITEM_ID,
                    quantity=5,
                ),
            },
        )
        menu_item_repo = InMemoryMenuItemRepository(
            {
                MENU_ITEM_ID: _menu_item(),
                OTHER_MENU_ITEM_ID: _menu_item(id=OTHER_MENU_ITEM_ID, name="Fries"),
            }
        )
        use_case = _use_case(order_repo, InMemoryPaymentRepository(), menu_item_repo=menu_item_repo)

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert [i.name for i in result.top_items] == ["Fries", "Burger"]
        assert [i.quantity_sold for i in result.top_items] == [5, 2]

    async def test_a_nonexistent_branch_raises(self) -> None:
        use_case = _use_case(
            InMemoryOrderRepository(),
            InMemoryPaymentRepository(),
            branch_repo=InMemoryBranchRepository(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

    async def test_an_empty_day_returns_zeroed_totals(self) -> None:
        use_case = _use_case(InMemoryOrderRepository(), InMemoryPaymentRepository())

        result = await use_case.execute(TENANT_ID, BRANCH_ID, REPORT_DATE)

        assert result.order_count == 0
        assert result.gross_sales_amount == Decimal(0)
        assert result.total_collected_amount == Decimal(0)
        assert result.tender_breakdown == []
        assert result.top_items == []
