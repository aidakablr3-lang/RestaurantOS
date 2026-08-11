"""Order entity -- aggregate root over its own ``OrderItem`` children.

Architecture doc SS3.1's graph: ``open -> fired -> served -> billed ->
closed``; ``open``/``fired -> voided``. Step 3 implemented ``fire()``,
``close()``, and ``void()``. Step 4 (Billing) adds ``mark_billed()`` --
called by ``GenerateBillUseCase`` once a Bill is created for the order.
``served`` stays a reachable *enum value* (the DB CHECK constraint
already allows it) with no domain method transitioning into it yet --
"kitchen finishes -> order marked served" as an automatic
cross-aggregate trigger is real, separate scope still not taken on, the
same "don't invent a business rule beyond what's specified" discipline
``Table.status`` followed in Sprint 5.

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

    def mark_billed(self) -> None:
        """The transition Step 4's ``GenerateBillUseCase`` reaches --
        this step's own contribution to the graph this entity's
        docstring already disclosed as unimplemented from Step 3 alone."""
        self._transition_to(
            OrderStatus.BILLED, allowed_from=(OrderStatus.FIRED, OrderStatus.SERVED)
        )

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
