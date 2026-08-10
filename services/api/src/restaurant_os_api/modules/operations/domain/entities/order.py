"""Order entity -- aggregate root over its own ``OrderItem`` children.

Architecture doc SS3.1's graph: ``open -> fired -> served -> billed ->
closed``; ``open``/``fired -> voided``. This step implements
``fire()``, ``close()``, and ``void()`` -- the three flat routes
Architecture doc SS6 actually specifies for Order. ``served``/``billed``
stay reachable *enum values* (the DB CHECK constraint already allows
them, and Step 4's Billing work will need to reach ``billed``) but no
domain method transitions into them from this step alone; wiring
"kitchen finishes -> order marked served" and "bill closes -> order
marked billed" as automatic cross-aggregate triggers is real, separate
scope this step deliberately doesn't take on, the same "don't invent a
business rule beyond what's specified" discipline ``Table.status``
followed in Sprint 5.

``close()`` deliberately accepts ``fired``, ``served``, *and* ``billed``
as valid predecessor states -- not just ``billed`` as a strict reading
of the linear graph would require. Reasoning, disclosed rather than
silently decided: Billing (Step 4) doesn't exist yet, so a strict
``billed``-only precondition would make ``close()`` unreachable through
this step's own routes alone. Closing directly from ``fired``/``served``
lets a full, testable order lifecycle exist today (e.g. a QR/takeaway
order with no dine-in billing step); once Billing exists, most real
orders will naturally reach ``closed`` via ``billed`` anyway, and this
looser precondition doesn't block that path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidOrderStatusTransitionError,
)


class OrderStatus(StrEnum):
    OPEN = "open"
    FIRED = "fired"
    SERVED = "served"
    BILLED = "billed"
    CLOSED = "closed"
    VOIDED = "voided"


class OrderSource(StrEnum):
    POS = "pos"
    QR = "qr"
    DELIVERY = "delivery"
    TAKEAWAY = "takeaway"


@dataclass(slots=True)
class Order:
    id: str
    tenant_id: str
    branch_id: str
    order_source: OrderSource
    status: OrderStatus
    subtotal_amount: Decimal
    tax_amount: Decimal
    currency_code: str
    opened_at: datetime
    created_at: datetime
    table_id: str | None = None
    tab_id: str | None = None
    customer_id: str | None = None
    closed_at: datetime | None = None
    origin_device_id: str | None = None

    def fire(self) -> None:
        self._transition_to(OrderStatus.FIRED, allowed_from=(OrderStatus.OPEN,))

    def close(self, *, closed_at: datetime) -> None:
        self._transition_to(
            OrderStatus.CLOSED,
            allowed_from=(OrderStatus.FIRED, OrderStatus.SERVED, OrderStatus.BILLED),
        )
        self.closed_at = closed_at

    def void(self) -> None:
        self._transition_to(OrderStatus.VOIDED, allowed_from=(OrderStatus.OPEN, OrderStatus.FIRED))

    def _transition_to(
        self, new_status: OrderStatus, *, allowed_from: tuple[OrderStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidOrderStatusTransitionError(self.id, self.status.value, new_status.value)
        self.status = new_status
