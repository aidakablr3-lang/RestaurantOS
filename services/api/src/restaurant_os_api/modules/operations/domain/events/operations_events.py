"""Operations module domain events (Architecture doc SS11), Order +
Kitchen slice. Framework-agnostic plain data, matching
``modules.restaurant.domain.events``'s exact convention -- each
satisfies the ``platform.events.DomainEvent`` structural contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class OrderPlaced:
    order_id: str
    branch_id: str
    order_source: str
    occurred_at: datetime

    event_type: ClassVar[str] = "OrderPlaced"
    aggregate_type: ClassVar[str] = "order"

    @property
    def aggregate_id(self) -> str:
        return self.order_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "orderId": self.order_id,
            "branchId": self.branch_id,
            "orderSource": self.order_source,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class OrderFired:
    order_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "OrderFired"
    aggregate_type: ClassVar[str] = "order"

    @property
    def aggregate_id(self) -> str:
        return self.order_id

    def to_payload(self) -> dict[str, Any]:
        return {"orderId": self.order_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class OrderServed:
    order_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "OrderServed"
    aggregate_type: ClassVar[str] = "order"

    @property
    def aggregate_id(self) -> str:
        return self.order_id

    def to_payload(self) -> dict[str, Any]:
        return {"orderId": self.order_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class OrderClosed:
    order_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "OrderClosed"
    aggregate_type: ClassVar[str] = "order"

    @property
    def aggregate_id(self) -> str:
        return self.order_id

    def to_payload(self) -> dict[str, Any]:
        return {"orderId": self.order_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class OrderVoided:
    order_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "OrderVoided"
    aggregate_type: ClassVar[str] = "order"

    @property
    def aggregate_id(self) -> str:
        return self.order_id

    def to_payload(self) -> dict[str, Any]:
        return {"orderId": self.order_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class TicketReady:
    """The event a future KDS/expo-screen WebSocket consumer subscribes
    to (Architecture doc SS11) -- published whenever a ``KitchenTicket``
    transitions to ``ready`` via its own status route."""

    kitchen_ticket_id: str
    order_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "TicketReady"
    aggregate_type: ClassVar[str] = "kitchen_ticket"

    @property
    def aggregate_id(self) -> str:
        return self.kitchen_ticket_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "kitchenTicketId": self.kitchen_ticket_id,
            "orderId": self.order_id,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PaymentSettled:
    payment_id: str
    bill_id: str
    amount: str
    occurred_at: datetime

    event_type: ClassVar[str] = "PaymentSettled"
    aggregate_type: ClassVar[str] = "payment"

    @property
    def aggregate_id(self) -> str:
        return self.payment_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "paymentId": self.payment_id,
            "billId": self.bill_id,
            "amount": self.amount,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class LowStockDetected:
    """Architecture doc SS11: published when a ``StockMovement`` insert
    crosses ``InventoryItem.reorder_point`` going downward -- the event
    a future menu-availability/86-list cache-invalidation consumer
    subscribes to. Only fires on the crossing itself (previous quantity
    above the point, resulting quantity at or below it), not on every
    movement that merely leaves the item already-low."""

    inventory_item_id: str
    branch_id: str
    quantity_on_hand: str
    reorder_point: str
    occurred_at: datetime

    event_type: ClassVar[str] = "LowStockDetected"
    aggregate_type: ClassVar[str] = "inventory_item"

    @property
    def aggregate_id(self) -> str:
        return self.inventory_item_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "inventoryItemId": self.inventory_item_id,
            "branchId": self.branch_id,
            "quantityOnHand": self.quantity_on_hand,
            "reorderPoint": self.reorder_point,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RefundProcessed:
    refund_id: str
    payment_id: str
    amount: str
    occurred_at: datetime

    event_type: ClassVar[str] = "RefundProcessed"
    aggregate_type: ClassVar[str] = "refund"

    @property
    def aggregate_id(self) -> str:
        return self.refund_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "refundId": self.refund_id,
            "paymentId": self.payment_id,
            "amount": self.amount,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PurchaseOrderReceived:
    """Architecture doc SS11: emitted by ``ConfirmGoodsReceiptUseCase``."""

    purchase_order_id: str
    goods_receipt_id: str
    has_discrepancy: bool
    occurred_at: datetime

    event_type: ClassVar[str] = "PurchaseOrderReceived"
    aggregate_type: ClassVar[str] = "purchase_order"

    @property
    def aggregate_id(self) -> str:
        return self.purchase_order_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "purchaseOrderId": self.purchase_order_id,
            "goodsReceiptId": self.goods_receipt_id,
            "hasDiscrepancy": self.has_discrepancy,
            "occurredAt": self.occurred_at.isoformat(),
        }
