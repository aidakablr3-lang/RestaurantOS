"""SQLAlchemy repository implementations for the operations module --
Order + Kitchen (Sprint 7 Step 3) and Billing + Payments + Ledger
(Sprint 7 Step 4). Mirrors
``modules.restaurant.infrastructure.database.repositories``'s exact
conventions.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_os_api.modules.operations.domain.entities import (
    Bill,
    BillAdjustment,
    BillAdjustmentType,
    BillStatus,
    CashDrawer,
    CashDrawerStatus,
    Discount,
    DiscountType,
    KitchenItem,
    KitchenItemStatus,
    KitchenTicket,
    KitchenTicketStatus,
    LedgerEntry,
    LedgerEntryType,
    Order,
    OrderItem,
    OrderItemLineStatus,
    OrderSource,
    OrderStatus,
    OrderTaxLine,
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
    Tab,
    TabStatus,
    Tax,
    TenderType,
)
from restaurant_os_api.modules.operations.infrastructure.database.models import (
    BillAdjustmentModel,
    BillModel,
    CashDrawerModel,
    DiscountModel,
    KitchenItemModel,
    KitchenTicketModel,
    LedgerEntryModel,
    OrderItemModel,
    OrderModel,
    OrderTaxLineModel,
    PaymentModel,
    RefundModel,
    TabModel,
    TaxModel,
)


def _order_from_model(model: OrderModel) -> Order:
    return Order(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        order_source=OrderSource(model.order_source),
        status=OrderStatus(model.status),
        subtotal_amount=model.subtotal_amount,
        tax_amount=model.tax_amount,
        currency_code=model.currency_code,
        opened_at=model.opened_at,
        created_at=model.created_at,
        table_id=model.table_id,
        tab_id=model.tab_id,
        customer_id=model.customer_id,
        closed_at=model.closed_at,
        origin_device_id=model.origin_device_id,
    )


def _order_item_from_model(model: OrderItemModel) -> OrderItem:
    return OrderItem(
        id=model.id,
        tenant_id=model.tenant_id,
        order_id=model.order_id,
        menu_item_id=model.menu_item_id,
        quantity=model.quantity,
        unit_price_amount=model.unit_price_amount,
        line_status=OrderItemLineStatus(model.line_status),
        created_at=model.created_at,
        modifiers_snapshot=model.modifiers_snapshot,
        recipe_cost_snapshot=model.recipe_cost_snapshot,
    )


def _tab_from_model(model: TabModel) -> Tab:
    return Tab(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        status=TabStatus(model.status),
        opened_at=model.opened_at,
        created_at=model.created_at,
        table_id=model.table_id,
        customer_id=model.customer_id,
        closed_at=model.closed_at,
    )


def _kitchen_ticket_from_model(model: KitchenTicketModel) -> KitchenTicket:
    return KitchenTicket(
        id=model.id,
        tenant_id=model.tenant_id,
        order_id=model.order_id,
        station=model.station,
        status=KitchenTicketStatus(model.status),
        created_at=model.created_at,
    )


def _kitchen_item_from_model(model: KitchenItemModel) -> KitchenItem:
    return KitchenItem(
        id=model.id,
        tenant_id=model.tenant_id,
        kitchen_ticket_id=model.kitchen_ticket_id,
        order_item_id=model.order_item_id,
        status=KitchenItemStatus(model.status),
        created_at=model.created_at,
    )


class SQLAlchemyOrderRepository:
    """Implements ``OrderRepository`` -- Order + its OrderItem children."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, order_id: str) -> Order | None:
        stmt = select(OrderModel).where(
            OrderModel.id == order_id, OrderModel.tenant_id == tenant_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _order_from_model(model) if model is not None else None

    async def create(self, order: Order) -> Order:
        model = OrderModel(
            id=order.id,
            tenant_id=order.tenant_id,
            branch_id=order.branch_id,
            table_id=order.table_id,
            tab_id=order.tab_id,
            customer_id=order.customer_id,
            order_source=order.order_source.value,
            status=order.status.value,
            subtotal_amount=order.subtotal_amount,
            tax_amount=order.tax_amount,
            currency_code=order.currency_code,
            opened_at=order.opened_at,
            closed_at=order.closed_at,
            origin_device_id=order.origin_device_id,
        )
        self._session.add(model)
        await self._session.flush()
        return _order_from_model(model)

    async def update(self, order: Order) -> Order:
        stmt = (
            update(OrderModel)
            .where(OrderModel.id == order.id, OrderModel.tenant_id == order.tenant_id)
            .values(
                table_id=order.table_id,
                tab_id=order.tab_id,
                status=order.status.value,
                subtotal_amount=order.subtotal_amount,
                tax_amount=order.tax_amount,
                closed_at=order.closed_at,
            )
        )
        await self._session.execute(stmt)
        return order

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[Order], int]:
        filters = (OrderModel.tenant_id == tenant_id, OrderModel.branch_id == branch_id)
        count_stmt = select(func.count()).select_from(OrderModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(OrderModel)
            .where(*filters)
            .order_by(OrderModel.opened_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_order_from_model(m) for m in models], total

    async def get_items(self, tenant_id: str, order_id: str) -> list[OrderItem]:
        stmt = (
            select(OrderItemModel)
            .where(OrderItemModel.tenant_id == tenant_id, OrderItemModel.order_id == order_id)
            .order_by(OrderItemModel.created_at)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_order_item_from_model(m) for m in models]

    async def get_item_by_id(self, tenant_id: str, order_item_id: str) -> OrderItem | None:
        stmt = select(OrderItemModel).where(
            OrderItemModel.id == order_item_id, OrderItemModel.tenant_id == tenant_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _order_item_from_model(model) if model is not None else None

    async def add_item(self, item: OrderItem) -> OrderItem:
        model = OrderItemModel(
            id=item.id,
            tenant_id=item.tenant_id,
            order_id=item.order_id,
            menu_item_id=item.menu_item_id,
            quantity=item.quantity,
            unit_price_amount=item.unit_price_amount,
            modifiers_snapshot=item.modifiers_snapshot,
            recipe_cost_snapshot=item.recipe_cost_snapshot,
            line_status=item.line_status.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _order_item_from_model(model)

    async def update_item(self, item: OrderItem) -> OrderItem:
        stmt = (
            update(OrderItemModel)
            .where(OrderItemModel.id == item.id, OrderItemModel.tenant_id == item.tenant_id)
            .values(line_status=item.line_status.value)
        )
        await self._session.execute(stmt)
        return item


class SQLAlchemyTabRepository:
    """Implements ``TabRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, tab_id: str) -> Tab | None:
        stmt = select(TabModel).where(TabModel.id == tab_id, TabModel.tenant_id == tenant_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _tab_from_model(model) if model is not None else None

    async def create(self, tab: Tab) -> Tab:
        model = TabModel(
            id=tab.id,
            tenant_id=tab.tenant_id,
            branch_id=tab.branch_id,
            table_id=tab.table_id,
            customer_id=tab.customer_id,
            status=tab.status.value,
            opened_at=tab.opened_at,
            closed_at=tab.closed_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _tab_from_model(model)

    async def update(self, tab: Tab) -> Tab:
        stmt = (
            update(TabModel)
            .where(TabModel.id == tab.id, TabModel.tenant_id == tab.tenant_id)
            .values(status=tab.status.value, closed_at=tab.closed_at)
        )
        await self._session.execute(stmt)
        return tab


class SQLAlchemyKitchenTicketRepository:
    """Implements ``KitchenTicketRepository`` -- KitchenTicket + its
    KitchenItem children."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, kitchen_ticket_id: str) -> KitchenTicket | None:
        stmt = select(KitchenTicketModel).where(
            KitchenTicketModel.id == kitchen_ticket_id, KitchenTicketModel.tenant_id == tenant_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _kitchen_ticket_from_model(model) if model is not None else None

    async def create(self, ticket: KitchenTicket) -> KitchenTicket:
        model = KitchenTicketModel(
            id=ticket.id,
            tenant_id=ticket.tenant_id,
            order_id=ticket.order_id,
            station=ticket.station,
            status=ticket.status.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _kitchen_ticket_from_model(model)

    async def update(self, ticket: KitchenTicket) -> KitchenTicket:
        stmt = (
            update(KitchenTicketModel)
            .where(
                KitchenTicketModel.id == ticket.id, KitchenTicketModel.tenant_id == ticket.tenant_id
            )
            .values(status=ticket.status.value)
        )
        await self._session.execute(stmt)
        return ticket

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[KitchenTicket], int]:
        # kitchen_tickets carries no branch_id column -- joins through
        # orders (Architecture doc SS9).
        filters = (
            KitchenTicketModel.tenant_id == tenant_id,
            OrderModel.branch_id == branch_id,
        )
        count_stmt = (
            select(func.count())
            .select_from(KitchenTicketModel)
            .join(OrderModel, OrderModel.id == KitchenTicketModel.order_id)
            .where(*filters)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(KitchenTicketModel)
            .join(OrderModel, OrderModel.id == KitchenTicketModel.order_id)
            .where(*filters)
            .order_by(KitchenTicketModel.created_at)
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_kitchen_ticket_from_model(m) for m in models], total

    async def get_items(self, tenant_id: str, kitchen_ticket_id: str) -> list[KitchenItem]:
        stmt = (
            select(KitchenItemModel)
            .where(
                KitchenItemModel.tenant_id == tenant_id,
                KitchenItemModel.kitchen_ticket_id == kitchen_ticket_id,
            )
            .order_by(KitchenItemModel.created_at)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_kitchen_item_from_model(m) for m in models]

    async def get_item_by_id(self, tenant_id: str, kitchen_item_id: str) -> KitchenItem | None:
        stmt = select(KitchenItemModel).where(
            KitchenItemModel.id == kitchen_item_id, KitchenItemModel.tenant_id == tenant_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _kitchen_item_from_model(model) if model is not None else None

    async def add_item(self, item: KitchenItem) -> KitchenItem:
        model = KitchenItemModel(
            id=item.id,
            tenant_id=item.tenant_id,
            kitchen_ticket_id=item.kitchen_ticket_id,
            order_item_id=item.order_item_id,
            status=item.status.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _kitchen_item_from_model(model)

    async def update_item(self, item: KitchenItem) -> KitchenItem:
        stmt = (
            update(KitchenItemModel)
            .where(KitchenItemModel.id == item.id, KitchenItemModel.tenant_id == item.tenant_id)
            .values(status=item.status.value)
        )
        await self._session.execute(stmt)
        return item


# --- Billing + Payments + Ledger mappers (Sprint 7 Step 4) ----------------


def _tax_from_model(model: TaxModel) -> Tax:
    return Tax(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        rate=model.rate,
        is_active=model.is_active,
        created_at=model.created_at,
    )


def _discount_from_model(model: DiscountModel) -> Discount:
    return Discount(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        discount_type=DiscountType(model.discount_type),
        value=model.value,
        requires_approval=model.requires_approval,
        created_at=model.created_at,
        max_value=model.max_value,
        active_from=model.active_from,
        active_to=model.active_to,
    )


def _bill_from_model(model: BillModel) -> Bill:
    return Bill(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        status=BillStatus(model.status),
        created_at=model.created_at,
        order_id=model.order_id,
        tab_id=model.tab_id,
    )


def _bill_adjustment_from_model(model: BillAdjustmentModel) -> BillAdjustment:
    return BillAdjustment(
        id=model.id,
        tenant_id=model.tenant_id,
        bill_id=model.bill_id,
        adjustment_type=BillAdjustmentType(model.adjustment_type),
        amount=model.amount,
        created_at=model.created_at,
        reference_type=model.reference_type,
        reference_id=model.reference_id,
        reason=model.reason,
        approved_by_user_id=model.approved_by_user_id,
    )


def _order_tax_line_from_model(model: OrderTaxLineModel) -> OrderTaxLine:
    return OrderTaxLine(
        id=model.id,
        tenant_id=model.tenant_id,
        order_id=model.order_id,
        tax_id=model.tax_id,
        taxable_amount=model.taxable_amount,
        tax_rate_snapshot=model.tax_rate_snapshot,
        tax_amount=model.tax_amount,
        created_at=model.created_at,
    )


def _payment_from_model(model: PaymentModel) -> Payment:
    return Payment(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        bill_id=model.bill_id,
        tender_type=TenderType(model.tender_type),
        amount=model.amount,
        currency_code=model.currency_code,
        tip_amount=model.tip_amount,
        status=PaymentStatus(model.status),
        created_at=model.created_at,
        gateway_token_ref=model.gateway_token_ref,
        gateway_last4=model.gateway_last4,
    )


def _refund_from_model(model: RefundModel) -> Refund:
    return Refund(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        payment_id=model.payment_id,
        order_id=model.order_id,
        approved_by_user_id=model.approved_by_user_id,
        amount=model.amount,
        status=RefundStatus(model.status),
        created_at=model.created_at,
    )


def _cash_drawer_from_model(model: CashDrawerModel) -> CashDrawer:
    return CashDrawer(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        status=CashDrawerStatus(model.status),
        opening_float_amount=model.opening_float_amount,
        opened_at=model.opened_at,
        created_at=model.created_at,
        terminal_id=model.terminal_id,
        closing_counted_amount=model.closing_counted_amount,
        closed_at=model.closed_at,
    )


class SQLAlchemyTaxRepository:
    """Implements ``TaxRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, tax_id: str) -> Tax | None:
        stmt = select(TaxModel).where(TaxModel.id == tax_id, TaxModel.tenant_id == tenant_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _tax_from_model(model) if model is not None else None

    async def create(self, tax: Tax) -> Tax:
        model = TaxModel(
            id=tax.id,
            tenant_id=tax.tenant_id,
            name=tax.name,
            rate=tax.rate,
            is_active=tax.is_active,
        )
        self._session.add(model)
        await self._session.flush()
        return _tax_from_model(model)

    async def list_active_for_tenant(self, tenant_id: str) -> list[Tax]:
        stmt = select(TaxModel).where(
            TaxModel.tenant_id == tenant_id,
            TaxModel.is_active.is_(True),
            TaxModel.deleted_at.is_(None),
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_tax_from_model(m) for m in models]


class SQLAlchemyDiscountRepository:
    """Implements ``DiscountRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, discount_id: str) -> Discount | None:
        stmt = select(DiscountModel).where(
            DiscountModel.id == discount_id,
            DiscountModel.tenant_id == tenant_id,
            DiscountModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _discount_from_model(model) if model is not None else None

    async def create(self, discount: Discount) -> Discount:
        model = DiscountModel(
            id=discount.id,
            tenant_id=discount.tenant_id,
            name=discount.name,
            discount_type=discount.discount_type.value,
            value=discount.value,
            requires_approval=discount.requires_approval,
            max_value=discount.max_value,
            active_from=discount.active_from,
            active_to=discount.active_to,
        )
        self._session.add(model)
        await self._session.flush()
        return _discount_from_model(model)

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Discount], int]:
        filters = (DiscountModel.tenant_id == tenant_id, DiscountModel.deleted_at.is_(None))
        count_stmt = select(func.count()).select_from(DiscountModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(DiscountModel)
            .where(*filters)
            .order_by(DiscountModel.name)
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_discount_from_model(m) for m in models], total


class SQLAlchemyBillRepository:
    """Implements ``BillRepository`` -- Bill + BillAdjustment + OrderTaxLine."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, bill_id: str) -> Bill | None:
        stmt = select(BillModel).where(BillModel.id == bill_id, BillModel.tenant_id == tenant_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _bill_from_model(model) if model is not None else None

    async def get_by_order_id(self, tenant_id: str, order_id: str) -> Bill | None:
        stmt = select(BillModel).where(
            BillModel.order_id == order_id, BillModel.tenant_id == tenant_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _bill_from_model(model) if model is not None else None

    async def create(self, bill: Bill) -> Bill:
        model = BillModel(
            id=bill.id,
            tenant_id=bill.tenant_id,
            branch_id=bill.branch_id,
            order_id=bill.order_id,
            tab_id=bill.tab_id,
            status=bill.status.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _bill_from_model(model)

    async def update(self, bill: Bill) -> Bill:
        stmt = (
            update(BillModel)
            .where(BillModel.id == bill.id, BillModel.tenant_id == bill.tenant_id)
            .values(status=bill.status.value)
        )
        await self._session.execute(stmt)
        return bill

    async def add_tax_line(self, tax_line: OrderTaxLine) -> OrderTaxLine:
        model = OrderTaxLineModel(
            id=tax_line.id,
            tenant_id=tax_line.tenant_id,
            order_id=tax_line.order_id,
            tax_id=tax_line.tax_id,
            taxable_amount=tax_line.taxable_amount,
            tax_rate_snapshot=tax_line.tax_rate_snapshot,
            tax_amount=tax_line.tax_amount,
        )
        self._session.add(model)
        await self._session.flush()
        return _order_tax_line_from_model(model)

    async def get_tax_lines_for_order(self, tenant_id: str, order_id: str) -> list[OrderTaxLine]:
        stmt = select(OrderTaxLineModel).where(
            OrderTaxLineModel.tenant_id == tenant_id, OrderTaxLineModel.order_id == order_id
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_order_tax_line_from_model(m) for m in models]

    async def add_adjustment(self, adjustment: BillAdjustment) -> BillAdjustment:
        model = BillAdjustmentModel(
            id=adjustment.id,
            tenant_id=adjustment.tenant_id,
            bill_id=adjustment.bill_id,
            adjustment_type=adjustment.adjustment_type.value,
            reference_type=adjustment.reference_type,
            reference_id=adjustment.reference_id,
            amount=adjustment.amount,
            reason=adjustment.reason,
            approved_by_user_id=adjustment.approved_by_user_id,
        )
        self._session.add(model)
        await self._session.flush()
        return _bill_adjustment_from_model(model)

    async def get_adjustments(self, tenant_id: str, bill_id: str) -> list[BillAdjustment]:
        stmt = select(BillAdjustmentModel).where(
            BillAdjustmentModel.tenant_id == tenant_id, BillAdjustmentModel.bill_id == bill_id
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_bill_adjustment_from_model(m) for m in models]


class SQLAlchemyPaymentRepository:
    """Implements ``PaymentRepository`` -- Payment + Refund."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, payment_id: str) -> Payment | None:
        stmt = select(PaymentModel).where(
            PaymentModel.id == payment_id, PaymentModel.tenant_id == tenant_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _payment_from_model(model) if model is not None else None

    async def create(self, payment: Payment) -> Payment:
        model = PaymentModel(
            id=payment.id,
            tenant_id=payment.tenant_id,
            branch_id=payment.branch_id,
            bill_id=payment.bill_id,
            tender_type=payment.tender_type.value,
            amount=payment.amount,
            currency_code=payment.currency_code,
            tip_amount=payment.tip_amount,
            gateway_token_ref=payment.gateway_token_ref,
            gateway_last4=payment.gateway_last4,
            status=payment.status.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _payment_from_model(model)

    async def update(self, payment: Payment) -> Payment:
        stmt = (
            update(PaymentModel)
            .where(PaymentModel.id == payment.id, PaymentModel.tenant_id == payment.tenant_id)
            .values(status=payment.status.value)
        )
        await self._session.execute(stmt)
        return payment

    async def list_for_bill(self, tenant_id: str, bill_id: str) -> list[Payment]:
        stmt = select(PaymentModel).where(
            PaymentModel.tenant_id == tenant_id, PaymentModel.bill_id == bill_id
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_payment_from_model(m) for m in models]

    async def get_refund_by_id(self, tenant_id: str, refund_id: str) -> Refund | None:
        stmt = select(RefundModel).where(
            RefundModel.id == refund_id, RefundModel.tenant_id == tenant_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _refund_from_model(model) if model is not None else None

    async def create_refund(self, refund: Refund) -> Refund:
        model = RefundModel(
            id=refund.id,
            tenant_id=refund.tenant_id,
            branch_id=refund.branch_id,
            payment_id=refund.payment_id,
            order_id=refund.order_id,
            approved_by_user_id=refund.approved_by_user_id,
            amount=refund.amount,
            status=refund.status.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _refund_from_model(model)

    async def update_refund(self, refund: Refund) -> Refund:
        stmt = (
            update(RefundModel)
            .where(RefundModel.id == refund.id, RefundModel.tenant_id == refund.tenant_id)
            .values(status=refund.status.value)
        )
        await self._session.execute(stmt)
        return refund

    async def list_refunds_for_payment(self, tenant_id: str, payment_id: str) -> list[Refund]:
        stmt = select(RefundModel).where(
            RefundModel.tenant_id == tenant_id, RefundModel.payment_id == payment_id
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_refund_from_model(m) for m in models]


class SQLAlchemyCashDrawerRepository:
    """Implements ``CashDrawerRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, cash_drawer_id: str) -> CashDrawer | None:
        stmt = select(CashDrawerModel).where(
            CashDrawerModel.id == cash_drawer_id, CashDrawerModel.tenant_id == tenant_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _cash_drawer_from_model(model) if model is not None else None

    async def get_open_for_branch(self, tenant_id: str, branch_id: str) -> CashDrawer | None:
        stmt = select(CashDrawerModel).where(
            CashDrawerModel.tenant_id == tenant_id,
            CashDrawerModel.branch_id == branch_id,
            CashDrawerModel.status == "open",
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _cash_drawer_from_model(model) if model is not None else None

    async def create(self, cash_drawer: CashDrawer) -> CashDrawer:
        model = CashDrawerModel(
            id=cash_drawer.id,
            tenant_id=cash_drawer.tenant_id,
            branch_id=cash_drawer.branch_id,
            terminal_id=cash_drawer.terminal_id,
            status=cash_drawer.status.value,
            opening_float_amount=cash_drawer.opening_float_amount,
            opened_at=cash_drawer.opened_at,
            closing_counted_amount=cash_drawer.closing_counted_amount,
            closed_at=cash_drawer.closed_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _cash_drawer_from_model(model)

    async def update(self, cash_drawer: CashDrawer) -> CashDrawer:
        stmt = (
            update(CashDrawerModel)
            .where(
                CashDrawerModel.id == cash_drawer.id,
                CashDrawerModel.tenant_id == cash_drawer.tenant_id,
            )
            .values(
                status=cash_drawer.status.value,
                closing_counted_amount=cash_drawer.closing_counted_amount,
                closed_at=cash_drawer.closed_at,
            )
        )
        await self._session.execute(stmt)
        return cash_drawer

    async def sum_settled_cash_payments(
        self, tenant_id: str, branch_id: str, *, since: datetime
    ) -> Decimal:
        stmt = select(func.coalesce(func.sum(PaymentModel.amount), 0)).where(
            PaymentModel.tenant_id == tenant_id,
            PaymentModel.branch_id == branch_id,
            PaymentModel.tender_type == "cash",
            PaymentModel.status == "settled",
            PaymentModel.created_at >= since,
        )
        total = (await self._session.execute(stmt)).scalar_one()
        return Decimal(total)


class SQLAlchemyLedgerRepository:
    """Implements ``LedgerRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: LedgerEntry) -> LedgerEntry:
        model = LedgerEntryModel(
            id=entry.id,
            tenant_id=entry.tenant_id,
            entry_type=entry.entry_type.value,
            account_code=entry.account_code,
            amount=entry.amount,
            currency_code=entry.currency_code,
            reference_type=entry.reference_type,
            reference_id=entry.reference_id,
        )
        self._session.add(model)
        await self._session.flush()
        return entry

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[LedgerEntry], int]:
        filters = (LedgerEntryModel.tenant_id == tenant_id,)
        count_stmt = select(func.count()).select_from(LedgerEntryModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(LedgerEntryModel)
            .where(*filters)
            .order_by(LedgerEntryModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        entries = [
            LedgerEntry(
                id=m.id,
                tenant_id=m.tenant_id,
                entry_type=LedgerEntryType(m.entry_type),
                account_code=m.account_code,
                amount=m.amount,
                currency_code=m.currency_code,
                created_at=m.created_at,
                reference_type=m.reference_type,
                reference_id=m.reference_id,
            )
            for m in models
        ]
        return entries, total
