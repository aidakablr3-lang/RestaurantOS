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
