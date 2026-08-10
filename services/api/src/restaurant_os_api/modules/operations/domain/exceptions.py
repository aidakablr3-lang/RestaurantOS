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
