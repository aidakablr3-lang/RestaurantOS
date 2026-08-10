"""OrderItem entity -- child of the Order aggregate, never persisted or
loaded independently of its parent Order.

Architecture doc SS3.1: "Added -> fired -> ready -> served; voidable
pre-fire only". This step implements ``fire()`` (called by
``FireOrderUseCase`` for every still-``ADDED`` item) and ``void()``
(pre-fire cancellation) -- ``ready``/``served`` are enum values the
DB CHECK constraint and future KDS-bump-to-order-item propagation need,
but no domain method transitions into them yet in this step, disclosed
the same way ``InvalidOrderStatusTransitionError`` discloses Order's
own unreached states.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidOrderItemStatusTransitionError,
)


class OrderItemLineStatus(StrEnum):
    ADDED = "added"
    FIRED = "fired"
    READY = "ready"
    SERVED = "served"
    VOIDED = "voided"


@dataclass(slots=True)
class OrderItem:
    id: str
    tenant_id: str
    order_id: str
    menu_item_id: str
    quantity: int
    unit_price_amount: Decimal
    line_status: OrderItemLineStatus
    created_at: datetime
    modifiers_snapshot: list[dict[str, Any]] = field(default_factory=list)
    recipe_cost_snapshot: Decimal | None = None

    def fire(self) -> None:
        self._transition_to(OrderItemLineStatus.FIRED, allowed_from=(OrderItemLineStatus.ADDED,))

    def void(self) -> None:
        self._transition_to(OrderItemLineStatus.VOIDED, allowed_from=(OrderItemLineStatus.ADDED,))

    def _transition_to(
        self, new_status: OrderItemLineStatus, *, allowed_from: tuple[OrderItemLineStatus, ...]
    ) -> None:
        if self.line_status not in allowed_from:
            raise InvalidOrderItemStatusTransitionError(
                self.id, self.line_status.value, new_status.value
            )
        self.line_status = new_status
