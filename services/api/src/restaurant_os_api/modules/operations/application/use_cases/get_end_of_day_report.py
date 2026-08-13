"""GetEndOfDayReportUseCase.

Backs the branch-nested ``GET /api/v1/branches/{branch_id}/reports/
end-of-day?date=YYYY-MM-DD`` -- the first reporting feature this
codebase has ever had (full-day operational simulation gap fix: no
report/summary/analytics feature existed anywhere before this).

``branch_id`` is already in the URL, so this follows
``GetOrderUseCase``/``ListOrdersUseCase``'s own minimal shape -- the
router's coarse ``require_branch_permission("reports.read")`` gate is
the only authorization check; no internal
``resolve_and_authorize_branch`` re-check is needed since there is no
second, flat identifier to resolve a *real* branch_id from (unlike
``FireOrderUseCase``'s order-derived branch).

``date`` is a bare calendar date, interpreted as one UTC day
``[00:00, 24:00)`` -- Branch carries no timezone column anywhere in
this codebase (confirmed against ``Branch``'s own fields), so there is
no per-branch "local day" this can resolve to yet; a disclosed scope
limit, not an oversight. Every aggregate here is computed at read time
from existing rows -- no new stored totals, mirroring
``CloseCashDrawerUseCase``'s own "reconciliation figure, not a second
source of truth" discipline.

Revenue figures come from **payments settled**, not orders opened, in
the window: ``Order``/``Payment``/``Refund`` all carry their own
``branch_id`` directly (denormalized), so this reads them independently
by branch+date rather than joining through Bill -- a payment settled
today against an order opened yesterday still counts as today's
collected revenue, matching how a real end-of-day cash-up works.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import (
    EndOfDayReportDTO,
    TenderBreakdownDTO,
    TopMenuItemDTO,
)
from restaurant_os_api.modules.operations.domain.entities import (
    OrderItem,
    OrderItemLineStatus,
    OrderStatus,
)
from restaurant_os_api.modules.operations.domain.ports import OrderRepository, PaymentRepository
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    RestaurantNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    MenuItemRepository,
    RestaurantRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_TOP_ITEMS_LIMIT = 5


def _quantity_by_menu_item(active_items: list[OrderItem]) -> dict[str, int]:
    quantities: dict[str, int] = {}
    for item in active_items:
        quantities[item.menu_item_id] = quantities.get(item.menu_item_id, 0) + item.quantity
    return quantities


class GetEndOfDayReportUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        payment_repository_factory: Callable[[AsyncSession], PaymentRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._restaurant_repository_factory = restaurant_repository_factory
        self._order_repository_factory = order_repository_factory
        self._payment_repository_factory = payment_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory

    async def execute(self, tenant_id: str, branch_id: str, report_date: date) -> EndOfDayReportDTO:
        start = datetime.combine(report_date, time.min, tzinfo=UTC)
        end = start + timedelta(days=1)

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            order_repo = self._order_repository_factory(uow.session)
            payment_repo = self._payment_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, branch_id)
            if branch is None:
                raise BranchNotFoundError(branch_id)
            restaurant = await restaurant_repo.get_by_id(tenant_id, branch.restaurant_id)
            if restaurant is None:
                raise RestaurantNotFoundError(branch.restaurant_id)

            orders = await order_repo.list_for_branch_opened_between(
                tenant_id, branch_id, start, end
            )
            order_ids = [o.id for o in orders]
            items = await order_repo.list_items_for_orders(tenant_id, order_ids)
            payments = await payment_repo.list_settled_for_branch_between(
                tenant_id, branch_id, start, end
            )
            refunds = await payment_repo.list_processed_refunds_for_branch_between(
                tenant_id, branch_id, start, end
            )

            voided_orders = [o for o in orders if o.status == OrderStatus.VOIDED]
            active_orders = [o for o in orders if o.status != OrderStatus.VOIDED]
            active_items = [i for i in items if i.line_status != OrderItemLineStatus.VOIDED]

            quantities = _quantity_by_menu_item(active_items)
            top_menu_item_ids = sorted(quantities, key=lambda mid: quantities[mid], reverse=True)[
                :_TOP_ITEMS_LIMIT
            ]

            top_items: list[TopMenuItemDTO] = []
            for menu_item_id in top_menu_item_ids:
                menu_item = await menu_item_repo.get_by_id(tenant_id, menu_item_id)
                top_items.append(
                    TopMenuItemDTO(
                        menu_item_id=menu_item_id,
                        name=menu_item.name if menu_item is not None else "Unknown item",
                        quantity_sold=quantities[menu_item_id],
                    )
                )

        gross_sales_amount = sum(
            (o.subtotal_amount + o.tax_amount for o in active_orders), Decimal(0)
        )
        voided_sales_amount = sum(
            (o.subtotal_amount + o.tax_amount for o in voided_orders), Decimal(0)
        )
        items_sold_count = sum(i.quantity for i in active_items)

        total_collected_amount = sum((p.amount for p in payments), Decimal(0))
        total_tips_amount = sum((p.tip_amount for p in payments), Decimal(0))
        total_refunded_amount = sum((r.amount for r in refunds), Decimal(0))
        net_collected_amount = total_collected_amount - total_refunded_amount

        tender_totals: dict[str, tuple[Decimal, int]] = {}
        for payment in payments:
            tender = payment.tender_type.value
            amount, count = tender_totals.get(tender, (Decimal(0), 0))
            tender_totals[tender] = (amount + payment.amount, count + 1)
        tender_breakdown = [
            TenderBreakdownDTO(tender_type=tender, amount=amount, payment_count=count)
            for tender, (amount, count) in sorted(tender_totals.items())
        ]

        return EndOfDayReportDTO(
            branch_id=branch_id,
            report_date=report_date.isoformat(),
            currency_code=restaurant.default_currency_code,
            order_count=len(active_orders),
            voided_order_count=len(voided_orders),
            items_sold_count=items_sold_count,
            gross_sales_amount=gross_sales_amount,
            voided_sales_amount=voided_sales_amount,
            total_collected_amount=total_collected_amount,
            total_tips_amount=total_tips_amount,
            total_refunded_amount=total_refunded_amount,
            net_collected_amount=net_collected_amount,
            tender_breakdown=tender_breakdown,
            top_items=top_items,
        )
