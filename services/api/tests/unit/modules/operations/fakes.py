"""In-memory test doubles for the operations module's ports.

Mirrors ``tests.unit.modules.restaurant.fakes``'s exact convention:
these implement the same ``Protocol`` interfaces the SQLAlchemy
repositories implement, so a use case under test cannot tell the
difference and no real database is ever touched. ``FakeAsyncSession``/
``fake_session_factory_returning``/``FakeResolveUserPermissionsUseCase``/
``FakeOutboxWriter`` are duplicated here rather than imported from the
restaurant module's own fakes -- the same per-module duplication
precedent ``tests.unit.modules.identity.fakes`` already established
(each module's own fakes are self-contained). Repositories the
operations module reuses directly from the restaurant module
(Branch/MenuItem/MenuCategory/Address) are imported from
``tests.unit.modules.restaurant.fakes`` instead of being duplicated,
since operations doesn't own those tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.operations.domain.entities import (
    Bill,
    BillAdjustment,
    CashDrawer,
    Discount,
    GoodsReceipt,
    InventoryCategory,
    InventoryItem,
    KitchenItem,
    KitchenTicket,
    LedgerEntry,
    Order,
    OrderItem,
    OrderStatus,
    OrderTaxLine,
    Payment,
    PaymentStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    Recipe,
    RecipeIngredient,
    Refund,
    RefundStatus,
    StockAdjustment,
    StockMovement,
    Supplier,
    Tab,
    Tax,
)
from restaurant_os_api.platform.events import DomainEvent


class FakeAsyncSession:
    """Stands in for ``AsyncSession`` wherever ``UnitOfWork`` needs one."""

    def __init__(self) -> None:
        self.executed_statements: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def execute(self, statement: object, params: object = None) -> None:
        self.executed_statements.append((statement, params))

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True


def fake_session_factory_returning(session: FakeAsyncSession):
    """Return a zero-arg callable matching ``async_sessionmaker``'s call shape."""

    def _factory() -> FakeAsyncSession:
        return session

    return _factory


@dataclass
class FakeResolveUserPermissionsUseCase:
    resolved: ResolvedPermissions = field(default_factory=ResolvedPermissions)

    async def execute(self, tenant_id: str, user_id: str) -> ResolvedPermissions:
        return self.resolved


@dataclass
class FakeOutboxWriter:
    published: list[tuple[str, DomainEvent]] = field(default_factory=list)

    async def publish(self, tenant_id: str, event: DomainEvent) -> None:
        self.published.append((tenant_id, event))


class InMemoryOrderRepository:
    """Implements ``OrderRepository`` -- bundles Order + OrderItem."""

    def __init__(
        self,
        orders: dict[str, Order] | None = None,
        items: dict[str, OrderItem] | None = None,
    ) -> None:
        self._orders = orders or {}
        self._items = items or {}

    async def get_by_id(self, tenant_id: str, order_id: str) -> Order | None:
        order = self._orders.get(order_id)
        if order is None or order.tenant_id != tenant_id:
            return None
        return order

    async def create(self, order: Order) -> Order:
        self._orders[order.id] = order
        return order

    async def update(self, order: Order) -> Order:
        self._orders[order.id] = order
        return order

    async def list_for_branch(
        self,
        tenant_id: str,
        branch_id: str,
        *,
        offset: int,
        limit: int,
        table_id: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Order], int]:
        visible = [
            o
            for o in self._orders.values()
            if o.tenant_id == tenant_id and o.branch_id == branch_id
        ]
        if table_id is not None:
            visible = [o for o in visible if o.table_id == table_id]
        if status is not None:
            visible = [o for o in visible if o.status.value == status]
        visible.sort(key=lambda o: o.opened_at, reverse=True)
        return visible[offset : offset + limit], len(visible)

    async def list_for_branch_opened_between(
        self, tenant_id: str, branch_id: str, start: datetime, end: datetime
    ) -> list[Order]:
        return [
            o
            for o in self._orders.values()
            if o.tenant_id == tenant_id and o.branch_id == branch_id and start <= o.opened_at < end
        ]

    async def has_active_orders_for_table(self, tenant_id: str, table_id: str) -> bool:
        return any(
            o.tenant_id == tenant_id
            and o.table_id == table_id
            and o.status not in (OrderStatus.CLOSED, OrderStatus.VOIDED)
            for o in self._orders.values()
        )

    async def list_items_for_orders(self, tenant_id: str, order_ids: list[str]) -> list[OrderItem]:
        return [
            i for i in self._items.values() if i.tenant_id == tenant_id and i.order_id in order_ids
        ]

    async def count_items_for_orders(self, tenant_id: str, order_ids: list[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self._items.values():
            if item.tenant_id == tenant_id and item.order_id in order_ids:
                counts[item.order_id] = counts.get(item.order_id, 0) + 1
        return counts

    async def get_items(self, tenant_id: str, order_id: str) -> list[OrderItem]:
        return [
            i for i in self._items.values() if i.tenant_id == tenant_id and i.order_id == order_id
        ]

    async def get_item_by_id(self, tenant_id: str, order_item_id: str) -> OrderItem | None:
        item = self._items.get(order_item_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    async def add_item(self, item: OrderItem) -> OrderItem:
        self._items[item.id] = item
        return item

    async def update_item(self, item: OrderItem) -> OrderItem:
        self._items[item.id] = item
        return item


class InMemoryTabRepository:
    def __init__(self, tabs: dict[str, Tab] | None = None) -> None:
        self._tabs = tabs or {}

    async def get_by_id(self, tenant_id: str, tab_id: str) -> Tab | None:
        tab = self._tabs.get(tab_id)
        if tab is None or tab.tenant_id != tenant_id:
            return None
        return tab

    async def create(self, tab: Tab) -> Tab:
        self._tabs[tab.id] = tab
        return tab

    async def update(self, tab: Tab) -> Tab:
        self._tabs[tab.id] = tab
        return tab


class InMemoryKitchenTicketRepository:
    """Implements ``KitchenTicketRepository`` -- bundles KitchenTicket +
    KitchenItem. ``list_for_branch`` fakes the real join through
    ``orders`` via an injected ``orders_by_id`` map."""

    def __init__(
        self,
        tickets: dict[str, KitchenTicket] | None = None,
        items: dict[str, KitchenItem] | None = None,
        orders_by_id: dict[str, Order] | None = None,
    ) -> None:
        self._tickets = tickets or {}
        self._items = items or {}
        self._orders_by_id = orders_by_id or {}

    async def get_by_id(self, tenant_id: str, kitchen_ticket_id: str) -> KitchenTicket | None:
        ticket = self._tickets.get(kitchen_ticket_id)
        if ticket is None or ticket.tenant_id != tenant_id:
            return None
        return ticket

    async def create(self, ticket: KitchenTicket) -> KitchenTicket:
        self._tickets[ticket.id] = ticket
        return ticket

    async def update(self, ticket: KitchenTicket) -> KitchenTicket:
        self._tickets[ticket.id] = ticket
        return ticket

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[KitchenTicket], int]:
        visible = [
            t
            for t in self._tickets.values()
            if t.tenant_id == tenant_id
            and self._orders_by_id.get(t.order_id) is not None
            and self._orders_by_id[t.order_id].branch_id == branch_id
        ]
        visible.sort(key=lambda t: t.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)

    async def get_items(self, tenant_id: str, kitchen_ticket_id: str) -> list[KitchenItem]:
        return [
            i
            for i in self._items.values()
            if i.tenant_id == tenant_id and i.kitchen_ticket_id == kitchen_ticket_id
        ]

    async def get_item_by_id(self, tenant_id: str, kitchen_item_id: str) -> KitchenItem | None:
        item = self._items.get(kitchen_item_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    async def add_item(self, item: KitchenItem) -> KitchenItem:
        self._items[item.id] = item
        return item

    async def update_item(self, item: KitchenItem) -> KitchenItem:
        self._items[item.id] = item
        return item


class InMemoryBillRepository:
    """Implements ``BillRepository`` -- bundles Bill + BillAdjustment +
    OrderTaxLine."""

    def __init__(
        self,
        bills: dict[str, Bill] | None = None,
        tax_lines: dict[str, OrderTaxLine] | None = None,
        adjustments: dict[str, BillAdjustment] | None = None,
    ) -> None:
        self._bills = bills or {}
        self._tax_lines = tax_lines or {}
        self._adjustments = adjustments or {}

    async def get_by_id(self, tenant_id: str, bill_id: str) -> Bill | None:
        bill = self._bills.get(bill_id)
        if bill is None or bill.tenant_id != tenant_id:
            return None
        return bill

    async def get_by_id_for_update(self, tenant_id: str, bill_id: str) -> Bill | None:
        # No real row locking against an in-memory dict -- these fakes
        # are single-threaded, so this is just an alias. The locking
        # behavior itself is only meaningfully provable against real
        # Postgres; see the integration regression test.
        return await self.get_by_id(tenant_id, bill_id)

    async def get_by_order_id(self, tenant_id: str, order_id: str) -> Bill | None:
        for bill in self._bills.values():
            if bill.tenant_id == tenant_id and bill.order_id == order_id:
                return bill
        return None

    async def create(self, bill: Bill) -> Bill:
        self._bills[bill.id] = bill
        return bill

    async def update(self, bill: Bill) -> Bill:
        self._bills[bill.id] = bill
        return bill

    async def add_tax_line(self, tax_line: OrderTaxLine) -> OrderTaxLine:
        self._tax_lines[tax_line.id] = tax_line
        return tax_line

    async def get_tax_lines_for_order(self, tenant_id: str, order_id: str) -> list[OrderTaxLine]:
        return [
            t
            for t in self._tax_lines.values()
            if t.tenant_id == tenant_id and t.order_id == order_id
        ]

    async def add_adjustment(self, adjustment: BillAdjustment) -> BillAdjustment:
        self._adjustments[adjustment.id] = adjustment
        return adjustment

    async def get_adjustments(self, tenant_id: str, bill_id: str) -> list[BillAdjustment]:
        return [
            a
            for a in self._adjustments.values()
            if a.tenant_id == tenant_id and a.bill_id == bill_id
        ]


class InMemoryDiscountRepository:
    def __init__(self, discounts: dict[str, Discount] | None = None) -> None:
        self._discounts = discounts or {}

    async def get_by_id(self, tenant_id: str, discount_id: str) -> Discount | None:
        discount = self._discounts.get(discount_id)
        if discount is None or discount.tenant_id != tenant_id:
            return None
        return discount

    async def create(self, discount: Discount) -> Discount:
        self._discounts[discount.id] = discount
        return discount

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Discount], int]:
        visible = [d for d in self._discounts.values() if d.tenant_id == tenant_id]
        visible.sort(key=lambda d: d.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)


class InMemoryPaymentRepository:
    """Implements ``PaymentRepository`` -- bundles Payment + Refund."""

    def __init__(
        self,
        payments: dict[str, Payment] | None = None,
        refunds: dict[str, Refund] | None = None,
    ) -> None:
        self._payments = payments or {}
        self._refunds = refunds or {}

    async def get_by_id(self, tenant_id: str, payment_id: str) -> Payment | None:
        payment = self._payments.get(payment_id)
        if payment is None or payment.tenant_id != tenant_id:
            return None
        return payment

    async def create(self, payment: Payment) -> Payment:
        self._payments[payment.id] = payment
        return payment

    async def update(self, payment: Payment) -> Payment:
        self._payments[payment.id] = payment
        return payment

    async def list_for_bill(self, tenant_id: str, bill_id: str) -> list[Payment]:
        return [
            p for p in self._payments.values() if p.tenant_id == tenant_id and p.bill_id == bill_id
        ]

    async def list_settled_for_branch_between(
        self, tenant_id: str, branch_id: str, start: datetime, end: datetime
    ) -> list[Payment]:
        return [
            p
            for p in self._payments.values()
            if p.tenant_id == tenant_id
            and p.branch_id == branch_id
            and p.status == PaymentStatus.SETTLED
            and start <= p.created_at < end
        ]

    async def get_refund_by_id(self, tenant_id: str, refund_id: str) -> Refund | None:
        refund = self._refunds.get(refund_id)
        if refund is None or refund.tenant_id != tenant_id:
            return None
        return refund

    async def create_refund(self, refund: Refund) -> Refund:
        self._refunds[refund.id] = refund
        return refund

    async def update_refund(self, refund: Refund) -> Refund:
        self._refunds[refund.id] = refund
        return refund

    async def list_refunds_for_payment(self, tenant_id: str, payment_id: str) -> list[Refund]:
        return [
            r
            for r in self._refunds.values()
            if r.tenant_id == tenant_id and r.payment_id == payment_id
        ]

    async def list_processed_refunds_for_branch_between(
        self, tenant_id: str, branch_id: str, start: datetime, end: datetime
    ) -> list[Refund]:
        return [
            r
            for r in self._refunds.values()
            if r.tenant_id == tenant_id
            and r.branch_id == branch_id
            and r.status == RefundStatus.PROCESSED
            and start <= r.created_at < end
        ]


class InMemoryCashDrawerRepository:
    def __init__(
        self,
        cash_drawers: dict[str, CashDrawer] | None = None,
        settled_cash_total: Decimal = Decimal(0),
    ) -> None:
        self._cash_drawers = cash_drawers or {}
        self._settled_cash_total = settled_cash_total

    async def get_by_id(self, tenant_id: str, cash_drawer_id: str) -> CashDrawer | None:
        drawer = self._cash_drawers.get(cash_drawer_id)
        if drawer is None or drawer.tenant_id != tenant_id:
            return None
        return drawer

    async def get_open_for_branch(self, tenant_id: str, branch_id: str) -> CashDrawer | None:
        for drawer in self._cash_drawers.values():
            if (
                drawer.tenant_id == tenant_id
                and drawer.branch_id == branch_id
                and drawer.status.value == "open"
            ):
                return drawer
        return None

    async def create(self, cash_drawer: CashDrawer) -> CashDrawer:
        self._cash_drawers[cash_drawer.id] = cash_drawer
        return cash_drawer

    async def update(self, cash_drawer: CashDrawer) -> CashDrawer:
        self._cash_drawers[cash_drawer.id] = cash_drawer
        return cash_drawer

    async def sum_settled_cash_payments(
        self, tenant_id: str, branch_id: str, *, since: datetime
    ) -> Decimal:
        return self._settled_cash_total


class InMemoryLedgerRepository:
    def __init__(self, entries: dict[str, LedgerEntry] | None = None) -> None:
        self._entries = entries or {}

    async def add(self, entry: LedgerEntry) -> LedgerEntry:
        self._entries[entry.id] = entry
        return entry

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[LedgerEntry], int]:
        visible = [e for e in self._entries.values() if e.tenant_id == tenant_id]
        visible.sort(key=lambda e: e.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)


class InMemoryTaxRepository:
    def __init__(self, taxes: dict[str, Tax] | None = None) -> None:
        self._taxes = taxes or {}

    async def get_by_id(self, tenant_id: str, tax_id: str) -> Tax | None:
        tax = self._taxes.get(tax_id)
        if tax is None or tax.tenant_id != tenant_id:
            return None
        return tax

    async def create(self, tax: Tax) -> Tax:
        self._taxes[tax.id] = tax
        return tax

    async def list_active_for_tenant(self, tenant_id: str) -> list[Tax]:
        return [t for t in self._taxes.values() if t.tenant_id == tenant_id and t.is_active]


class InMemoryInventoryCategoryRepository:
    def __init__(self, categories: dict[str, InventoryCategory] | None = None) -> None:
        self._categories = categories or {}

    async def get_by_id(
        self, tenant_id: str, inventory_category_id: str
    ) -> InventoryCategory | None:
        category = self._categories.get(inventory_category_id)
        if category is None or category.tenant_id != tenant_id:
            return None
        return category

    async def get_by_tenant_id_and_name(
        self, tenant_id: str, name: str
    ) -> InventoryCategory | None:
        for category in self._categories.values():
            if category.tenant_id == tenant_id and category.name == name:
                return category
        return None

    async def create(self, category: InventoryCategory) -> InventoryCategory:
        self._categories[category.id] = category
        return category

    async def list_for_tenant(self, tenant_id: str) -> list[InventoryCategory]:
        return [c for c in self._categories.values() if c.tenant_id == tenant_id]


class InMemoryInventoryItemRepository:
    def __init__(self, items: dict[str, InventoryItem] | None = None) -> None:
        self._items = items or {}

    async def get_by_id(self, tenant_id: str, inventory_item_id: str) -> InventoryItem | None:
        item = self._items.get(inventory_item_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    async def get_by_branch_id_and_name(
        self, tenant_id: str, branch_id: str, name: str
    ) -> InventoryItem | None:
        for item in self._items.values():
            if item.tenant_id == tenant_id and item.branch_id == branch_id and item.name == name:
                return item
        return None

    async def create(self, item: InventoryItem) -> InventoryItem:
        self._items[item.id] = item
        return item

    async def update(self, item: InventoryItem) -> InventoryItem:
        self._items[item.id] = item
        return item

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[InventoryItem], int]:
        visible = [
            i for i in self._items.values() if i.tenant_id == tenant_id and i.branch_id == branch_id
        ]
        visible.sort(key=lambda i: i.name)
        return visible[offset : offset + limit], len(visible)


class InMemoryStockMovementRepository:
    """Implements ``StockMovementRepository`` -- bundles StockMovement +
    StockAdjustment. Applies the movement's ``quantity_delta`` to the
    linked ``InventoryItem`` in the injected ``inventory_items`` map,
    faking the real ``stock_movements`` trigger's own balance
    maintenance -- callers reading the item back through
    ``InMemoryInventoryItemRepository`` (sharing the same dict) see the
    updated balance, matching the real "fresh repository read" pattern
    the use cases themselves rely on."""

    def __init__(
        self,
        movements: dict[str, StockMovement] | None = None,
        adjustments: dict[str, StockAdjustment] | None = None,
        inventory_items: dict[str, InventoryItem] | None = None,
    ) -> None:
        self._movements = movements or {}
        self._adjustments = adjustments or {}
        self._inventory_items = inventory_items if inventory_items is not None else {}

    async def create_movement(self, movement: StockMovement) -> StockMovement:
        self._movements[movement.id] = movement
        item = self._inventory_items.get(movement.inventory_item_id)
        if item is not None:
            item.quantity_on_hand = item.quantity_on_hand + movement.quantity_delta
        return movement

    async def list_for_item(
        self, tenant_id: str, inventory_item_id: str, *, offset: int, limit: int
    ) -> tuple[list[StockMovement], int]:
        visible = [
            m
            for m in self._movements.values()
            if m.tenant_id == tenant_id and m.inventory_item_id == inventory_item_id
        ]
        visible.sort(key=lambda m: m.occurred_at, reverse=True)
        return visible[offset : offset + limit], len(visible)

    async def create_adjustment(self, adjustment: StockAdjustment) -> StockAdjustment:
        self._adjustments[adjustment.id] = adjustment
        return adjustment


class InMemoryRecipeRepository:
    """Implements ``RecipeRepository`` -- bundles Recipe + RecipeIngredient."""

    def __init__(
        self,
        recipes: dict[str, Recipe] | None = None,
        ingredients: dict[str, RecipeIngredient] | None = None,
    ) -> None:
        self._recipes = recipes or {}
        self._ingredients = ingredients or {}

    async def get_by_id(self, tenant_id: str, recipe_id: str) -> Recipe | None:
        recipe = self._recipes.get(recipe_id)
        if recipe is None or recipe.tenant_id != tenant_id:
            return None
        return recipe

    async def create(self, recipe: Recipe) -> Recipe:
        self._recipes[recipe.id] = recipe
        return recipe

    async def update(self, recipe: Recipe) -> Recipe:
        self._recipes[recipe.id] = recipe
        return recipe

    async def add_ingredient(self, ingredient: RecipeIngredient) -> RecipeIngredient:
        self._ingredients[ingredient.id] = ingredient
        return ingredient

    async def list_ingredients_for_recipe(
        self, tenant_id: str, recipe_id: str
    ) -> list[RecipeIngredient]:
        return [
            i
            for i in self._ingredients.values()
            if i.tenant_id == tenant_id and i.recipe_id == recipe_id
        ]


class InMemorySupplierRepository:
    def __init__(self, suppliers: dict[str, Supplier] | None = None) -> None:
        self._suppliers = suppliers or {}

    async def get_by_id(self, tenant_id: str, supplier_id: str) -> Supplier | None:
        supplier = self._suppliers.get(supplier_id)
        if supplier is None or supplier.tenant_id != tenant_id:
            return None
        return supplier

    async def get_by_tenant_id_and_name(self, tenant_id: str, name: str) -> Supplier | None:
        for supplier in self._suppliers.values():
            if supplier.tenant_id == tenant_id and supplier.name == name:
                return supplier
        return None

    async def create(self, supplier: Supplier) -> Supplier:
        self._suppliers[supplier.id] = supplier
        return supplier

    async def update(self, supplier: Supplier) -> Supplier:
        self._suppliers[supplier.id] = supplier
        return supplier

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Supplier], int]:
        visible = [s for s in self._suppliers.values() if s.tenant_id == tenant_id]
        visible.sort(key=lambda s: s.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)


class InMemoryPurchaseOrderRepository:
    """Implements ``PurchaseOrderRepository`` -- bundles PurchaseOrder +
    PurchaseOrderItem."""

    def __init__(
        self,
        purchase_orders: dict[str, PurchaseOrder] | None = None,
        items: dict[str, PurchaseOrderItem] | None = None,
    ) -> None:
        self._purchase_orders = purchase_orders or {}
        self._items = items or {}

    async def get_by_id(self, tenant_id: str, purchase_order_id: str) -> PurchaseOrder | None:
        po = self._purchase_orders.get(purchase_order_id)
        if po is None or po.tenant_id != tenant_id:
            return None
        return po

    async def create(self, purchase_order: PurchaseOrder) -> PurchaseOrder:
        self._purchase_orders[purchase_order.id] = purchase_order
        return purchase_order

    async def update(self, purchase_order: PurchaseOrder) -> PurchaseOrder:
        self._purchase_orders[purchase_order.id] = purchase_order
        return purchase_order

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[PurchaseOrder], int]:
        visible = [
            po
            for po in self._purchase_orders.values()
            if po.tenant_id == tenant_id and po.branch_id == branch_id
        ]
        visible.sort(key=lambda po: po.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)

    async def get_items(self, tenant_id: str, purchase_order_id: str) -> list[PurchaseOrderItem]:
        return [
            i
            for i in self._items.values()
            if i.tenant_id == tenant_id and i.purchase_order_id == purchase_order_id
        ]

    async def get_item_by_id(
        self, tenant_id: str, purchase_order_item_id: str
    ) -> PurchaseOrderItem | None:
        item = self._items.get(purchase_order_item_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    async def add_item(self, item: PurchaseOrderItem) -> PurchaseOrderItem:
        self._items[item.id] = item
        return item

    async def update_item(self, item: PurchaseOrderItem) -> PurchaseOrderItem:
        self._items[item.id] = item
        return item


class InMemoryGoodsReceiptRepository:
    def __init__(self, goods_receipts: dict[str, GoodsReceipt] | None = None) -> None:
        self._goods_receipts = goods_receipts or {}

    async def create(self, goods_receipt: GoodsReceipt) -> GoodsReceipt:
        self._goods_receipts[goods_receipt.id] = goods_receipt
        return goods_receipt

    async def update(self, goods_receipt: GoodsReceipt) -> GoodsReceipt:
        self._goods_receipts[goods_receipt.id] = goods_receipt
        return goods_receipt
