"""SQLAlchemy repository implementations for the operations module,
Order + Kitchen slice (Sprint 7 Step 3). Mirrors
``modules.restaurant.infrastructure.database.repositories``'s exact
conventions.
"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_os_api.modules.operations.domain.entities import (
    KitchenItem,
    KitchenItemStatus,
    KitchenTicket,
    KitchenTicketStatus,
    Order,
    OrderItem,
    OrderItemLineStatus,
    OrderSource,
    OrderStatus,
    Tab,
    TabStatus,
)
from restaurant_os_api.modules.operations.infrastructure.database.models import (
    KitchenItemModel,
    KitchenTicketModel,
    OrderItemModel,
    OrderModel,
    TabModel,
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
