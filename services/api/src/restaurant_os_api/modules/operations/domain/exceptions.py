"""Domain exceptions for the operations module.

Mirrors ``modules.restaurant.domain.exceptions``'s exact shape: no HTTP
concepts here, a stable ``error_code`` per exception, registered in
``core/exceptions.py``'s ``_STATUS_BY_ERROR_CODE`` once the presentation
layer exists to raise them.
"""

from __future__ import annotations


class OperationsDomainError(Exception):
    """Base class for every domain exception raised by the operations module."""

    error_code: str = "OPERATIONS_DOMAIN_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class OrderNotFoundError(OperationsDomainError):
    error_code = "ORDER_NOT_FOUND"

    def __init__(self, order_id: str) -> None:
        super().__init__(f"Order '{order_id}' does not exist.")
        self.order_id = order_id


class InvalidOrderStatusTransitionError(OperationsDomainError):
    """The graph is Architecture-doc-specified (SS3.1):
    ``open -> fired -> served -> billed -> closed``, ``open``/``fired
    -> voided``. This step implements ``fire()``/``close()``/``void()``
    only -- ``served``/``billed`` are reachable states the enum still
    defines, but no domain method transitions into them yet (Kitchen-
    driven serve completion and Billing generation are their own future
    triggers, deliberately not auto-wired here -- see ``order.py``'s own
    docstring)."""

    error_code = "INVALID_ORDER_STATUS_TRANSITION"

    def __init__(self, order_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Order '{order_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.order_id = order_id
        self.from_status = from_status
        self.to_status = to_status


class OrderHasNoItemsError(OperationsDomainError):
    """Firing an order with zero (non-voided) items would create an
    empty KitchenTicket -- rejected proactively rather than left as a
    silently-useless ticket."""

    error_code = "ORDER_HAS_NO_ITEMS"

    def __init__(self, order_id: str) -> None:
        super().__init__(f"Order '{order_id}' has no items to fire.")
        self.order_id = order_id


class OrderItemNotFoundError(OperationsDomainError):
    error_code = "ORDER_ITEM_NOT_FOUND"

    def __init__(self, order_item_id: str) -> None:
        super().__init__(f"OrderItem '{order_item_id}' does not exist.")
        self.order_item_id = order_item_id


class InvalidOrderItemStatusTransitionError(OperationsDomainError):
    error_code = "INVALID_ORDER_ITEM_STATUS_TRANSITION"

    def __init__(self, order_item_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"OrderItem '{order_item_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.order_item_id = order_item_id
        self.from_status = from_status
        self.to_status = to_status


class MenuItemNotAvailableError(OperationsDomainError):
    """The item exists (a plain not-found would be
    ``restaurant.domain.exceptions.MenuItemNotFoundError``, reused
    as-is since Operations doesn't own ``MenuItem``) but its own
    ``is_available`` flag is false. Full time-windowed availability
    resolution (``MenuItemAvailability`` override rows) is not checked
    here -- a disclosed scope-narrowing, see ``add_order_item.py``."""

    error_code = "MENU_ITEM_NOT_AVAILABLE"

    def __init__(self, menu_item_id: str) -> None:
        super().__init__(f"MenuItem '{menu_item_id}' is not available.")
        self.menu_item_id = menu_item_id


class TabNotFoundError(OperationsDomainError):
    error_code = "TAB_NOT_FOUND"

    def __init__(self, tab_id: str) -> None:
        super().__init__(f"Tab '{tab_id}' does not exist.")
        self.tab_id = tab_id


class InvalidTabStatusTransitionError(OperationsDomainError):
    error_code = "INVALID_TAB_STATUS_TRANSITION"

    def __init__(self, tab_id: str, from_status: str, to_status: str) -> None:
        super().__init__(f"Tab '{tab_id}' cannot transition from '{from_status}' to '{to_status}'.")
        self.tab_id = tab_id
        self.from_status = from_status
        self.to_status = to_status


class KitchenTicketNotFoundError(OperationsDomainError):
    error_code = "KITCHEN_TICKET_NOT_FOUND"

    def __init__(self, kitchen_ticket_id: str) -> None:
        super().__init__(f"KitchenTicket '{kitchen_ticket_id}' does not exist.")
        self.kitchen_ticket_id = kitchen_ticket_id


class InvalidKitchenTicketStatusTransitionError(OperationsDomainError):
    error_code = "INVALID_KITCHEN_TICKET_STATUS_TRANSITION"

    def __init__(self, kitchen_ticket_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"KitchenTicket '{kitchen_ticket_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.kitchen_ticket_id = kitchen_ticket_id
        self.from_status = from_status
        self.to_status = to_status


class KitchenItemNotFoundError(OperationsDomainError):
    error_code = "KITCHEN_ITEM_NOT_FOUND"

    def __init__(self, kitchen_item_id: str) -> None:
        super().__init__(f"KitchenItem '{kitchen_item_id}' does not exist.")
        self.kitchen_item_id = kitchen_item_id


class InvalidKitchenItemStatusTransitionError(OperationsDomainError):
    error_code = "INVALID_KITCHEN_ITEM_STATUS_TRANSITION"

    def __init__(self, kitchen_item_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"KitchenItem '{kitchen_item_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.kitchen_item_id = kitchen_item_id
        self.from_status = from_status
        self.to_status = to_status


# --- Billing + Payments + Ledger (Sprint 7 Step 4) -----------------------


class BillNotFoundError(OperationsDomainError):
    error_code = "BILL_NOT_FOUND"

    def __init__(self, bill_id: str) -> None:
        super().__init__(f"Bill '{bill_id}' does not exist.")
        self.bill_id = bill_id


class BillAlreadyClosedError(OperationsDomainError):
    error_code = "BILL_ALREADY_CLOSED"

    def __init__(self, bill_id: str) -> None:
        super().__init__(f"Bill '{bill_id}' is already closed.")
        self.bill_id = bill_id


class BillAlreadyExistsError(OperationsDomainError):
    """One Order/Tab gets at most one Bill -- generating a second one
    for the same Order/Tab is rejected rather than silently creating a
    duplicate."""

    error_code = "BILL_ALREADY_EXISTS"

    def __init__(self, order_id: str | None, tab_id: str | None) -> None:
        target = order_id or tab_id
        super().__init__(f"A bill already exists for '{target}'.")
        self.order_id = order_id
        self.tab_id = tab_id


class DiscountNotFoundError(OperationsDomainError):
    error_code = "DISCOUNT_NOT_FOUND"

    def __init__(self, discount_id: str) -> None:
        super().__init__(f"Discount '{discount_id}' does not exist.")
        self.discount_id = discount_id


class AdjustmentApprovalRequiredError(OperationsDomainError):
    """Mirrors ``Discount.requires_approval`` -- applying a discount
    flagged this way without an ``approved_by_user_id`` is rejected."""

    error_code = "ADJUSTMENT_APPROVAL_REQUIRED"

    def __init__(self, discount_id: str) -> None:
        super().__init__(f"Discount '{discount_id}' requires an approver.")
        self.discount_id = discount_id


class PaymentNotFoundError(OperationsDomainError):
    error_code = "PAYMENT_NOT_FOUND"

    def __init__(self, payment_id: str) -> None:
        super().__init__(f"Payment '{payment_id}' does not exist.")
        self.payment_id = payment_id


class InvalidPaymentStatusTransitionError(OperationsDomainError):
    error_code = "INVALID_PAYMENT_STATUS_TRANSITION"

    def __init__(self, payment_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Payment '{payment_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.payment_id = payment_id
        self.from_status = from_status
        self.to_status = to_status


class OverpaymentError(OperationsDomainError):
    """A payment that would take the bill's total paid amount above its
    amount due -- rejected rather than silently accepted as a credit
    balance (no credit/store-value concept exists in this scope)."""

    error_code = "OVERPAYMENT"

    def __init__(self, bill_id: str, amount_due: str, attempted_total: str) -> None:
        super().__init__(
            f"Bill '{bill_id}' amount due is {amount_due}; payments would total {attempted_total}."
        )
        self.bill_id = bill_id


class RefundNotFoundError(OperationsDomainError):
    error_code = "REFUND_NOT_FOUND"

    def __init__(self, refund_id: str) -> None:
        super().__init__(f"Refund '{refund_id}' does not exist.")
        self.refund_id = refund_id


class InvalidRefundStatusTransitionError(OperationsDomainError):
    error_code = "INVALID_REFUND_STATUS_TRANSITION"

    def __init__(self, refund_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Refund '{refund_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.refund_id = refund_id
        self.from_status = from_status
        self.to_status = to_status


class RefundExceedsPaymentError(OperationsDomainError):
    error_code = "REFUND_EXCEEDS_PAYMENT"

    def __init__(self, payment_id: str) -> None:
        super().__init__(
            f"Refund amount exceeds the remaining refundable balance of payment '{payment_id}'."
        )
        self.payment_id = payment_id


class CashDrawerNotFoundError(OperationsDomainError):
    error_code = "CASH_DRAWER_NOT_FOUND"

    def __init__(self, cash_drawer_id: str) -> None:
        super().__init__(f"CashDrawer '{cash_drawer_id}' does not exist.")
        self.cash_drawer_id = cash_drawer_id


class InvalidCashDrawerStatusTransitionError(OperationsDomainError):
    error_code = "INVALID_CASH_DRAWER_STATUS_TRANSITION"

    def __init__(self, cash_drawer_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"CashDrawer '{cash_drawer_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.cash_drawer_id = cash_drawer_id
        self.from_status = from_status
        self.to_status = to_status


class CashDrawerAlreadyOpenError(OperationsDomainError):
    """At most one open CashDrawer per branch (+ optional terminal) at a
    time -- opening a second one is rejected rather than silently
    allowed, which would make "which drawer is this cash payment
    against" ambiguous."""

    error_code = "CASH_DRAWER_ALREADY_OPEN"

    def __init__(self, branch_id: str) -> None:
        super().__init__(f"Branch '{branch_id}' already has an open cash drawer.")
        self.branch_id = branch_id


# --- Inventory + Recipe (Sprint 7 Step 5) ---------------------------------


class RecipeNotFoundError(OperationsDomainError):
    error_code = "RECIPE_NOT_FOUND"

    def __init__(self, recipe_id: str) -> None:
        super().__init__(f"Recipe '{recipe_id}' does not exist.")
        self.recipe_id = recipe_id


class InventoryCategoryNotFoundError(OperationsDomainError):
    error_code = "INVENTORY_CATEGORY_NOT_FOUND"

    def __init__(self, inventory_category_id: str) -> None:
        super().__init__(f"InventoryCategory '{inventory_category_id}' does not exist.")
        self.inventory_category_id = inventory_category_id


class InventoryCategoryNameConflictError(OperationsDomainError):
    """Mirrors the DB's own ``UNIQUE (tenant_id, name)`` constraint,
    checked proactively the same way ``MenuCategoryNameConflictError``
    checks its own uniqueness constraint."""

    error_code = "INVENTORY_CATEGORY_NAME_CONFLICT"

    def __init__(self, name: str) -> None:
        super().__init__(f"An InventoryCategory named '{name}' already exists.")
        self.name = name


class InventoryItemNotFoundError(OperationsDomainError):
    error_code = "INVENTORY_ITEM_NOT_FOUND"

    def __init__(self, inventory_item_id: str) -> None:
        super().__init__(f"InventoryItem '{inventory_item_id}' does not exist.")
        self.inventory_item_id = inventory_item_id


class InventoryItemNameConflictError(OperationsDomainError):
    """Mirrors the DB's own ``UNIQUE (branch_id, name)`` constraint."""

    error_code = "INVENTORY_ITEM_NAME_CONFLICT"

    def __init__(self, branch_id: str, name: str) -> None:
        super().__init__(f"Branch '{branch_id}' already has an InventoryItem named '{name}'.")
        self.branch_id = branch_id
        self.name = name


class InsufficientStockError(OperationsDomainError):
    """Application-layer replica of the ``stock_movements`` trigger's own
    check (Data Architecture v2.0 Group D) -- ``RecordStockMovementUseCase``
    evaluates the same ``COALESCE(item_override, branch_allows_negative,
    false)`` precedence *before* inserting, purely to raise a clean,
    typed domain error instead of a raw database exception. The trigger
    itself remains the actual source of truth and still re-checks at
    insert time (defense in depth), matching this codebase's existing
    "pre-check for a clean error, DB constraint is still the real
    enforcement" shape (e.g. ``BillAlreadyExistsError`` vs. the bill
    XOR constraint)."""

    error_code = "INSUFFICIENT_STOCK"

    def __init__(self, inventory_item_id: str, current_quantity: str, attempted_delta: str) -> None:
        super().__init__(
            f"InventoryItem '{inventory_item_id}' has {current_quantity} on hand; "
            f"a delta of {attempted_delta} would take it negative."
        )
        self.inventory_item_id = inventory_item_id


class StockAdjustmentRequiresReasonError(OperationsDomainError):
    """``movement_type='adjustment'`` always creates a linked
    ``StockAdjustment`` row (Architecture doc SS3.6) -- a reason and an
    approver are required for that specific movement type, matching
    ``Refund``'s own "requires an approver" precedent."""

    error_code = "STOCK_ADJUSTMENT_REQUIRES_REASON"

    def __init__(self) -> None:
        super().__init__("An 'adjustment' stock movement requires a reason and an approving user.")


# --- Purchasing (Sprint 7 Step 6) -----------------------------------------


class SupplierNotFoundError(OperationsDomainError):
    error_code = "SUPPLIER_NOT_FOUND"

    def __init__(self, supplier_id: str) -> None:
        super().__init__(f"Supplier '{supplier_id}' does not exist.")
        self.supplier_id = supplier_id


class SupplierNameConflictError(OperationsDomainError):
    """Mirrors the DB's own ``UNIQUE (tenant_id, name)`` constraint."""

    error_code = "SUPPLIER_NAME_CONFLICT"

    def __init__(self, name: str) -> None:
        super().__init__(f"A Supplier named '{name}' already exists.")
        self.name = name


class PurchaseOrderNotFoundError(OperationsDomainError):
    error_code = "PURCHASE_ORDER_NOT_FOUND"

    def __init__(self, purchase_order_id: str) -> None:
        super().__init__(f"PurchaseOrder '{purchase_order_id}' does not exist.")
        self.purchase_order_id = purchase_order_id


class InvalidPurchaseOrderStatusTransitionError(OperationsDomainError):
    error_code = "INVALID_PURCHASE_ORDER_STATUS_TRANSITION"

    def __init__(self, purchase_order_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"PurchaseOrder '{purchase_order_id}' cannot transition from "
            f"'{from_status}' to '{to_status}'."
        )
        self.purchase_order_id = purchase_order_id
        self.from_status = from_status
        self.to_status = to_status


class PurchaseOrderHasNoItemsError(OperationsDomainError):
    """Sending a PO with zero line items would create a meaningless
    order to the supplier -- rejected proactively, mirroring
    ``OrderHasNoItemsError``'s own precedent for firing an empty order."""

    error_code = "PURCHASE_ORDER_HAS_NO_ITEMS"

    def __init__(self, purchase_order_id: str) -> None:
        super().__init__(f"PurchaseOrder '{purchase_order_id}' has no items to send.")
        self.purchase_order_id = purchase_order_id


class PurchaseOrderItemNotFoundError(OperationsDomainError):
    error_code = "PURCHASE_ORDER_ITEM_NOT_FOUND"

    def __init__(self, purchase_order_item_id: str) -> None:
        super().__init__(f"PurchaseOrderItem '{purchase_order_item_id}' does not exist.")
        self.purchase_order_item_id = purchase_order_item_id


class InvalidGoodsReceiptStatusTransitionError(OperationsDomainError):
    error_code = "INVALID_GOODS_RECEIPT_STATUS_TRANSITION"

    def __init__(self, goods_receipt_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"GoodsReceipt '{goods_receipt_id}' cannot transition from "
            f"'{from_status}' to '{to_status}'."
        )
        self.goods_receipt_id = goods_receipt_id
        self.from_status = from_status
        self.to_status = to_status
