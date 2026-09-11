"""Shared kitchen-ticket cancellation cascade -- the operational-gap
fix (2026-09-08) for a long-disclosed limitation: ``VoidOrderUseCase``
used to void the ``Order`` and stop there, leaving any already-fired
``KitchenTicket`` sitting on the KDS in whatever status it was in, with
nothing telling the kitchen to stop. Extracted so a future single-item
post-fire cancellation route (the gap ``void_order_item.py``'s own
docstring already names) can reuse the same per-ticket logic instead of
duplicating it, matching this module's established "extracted, not
duplicated" convention (``_table_release.py``, ``_recipe_deduction.py``).

Only ever claims tickets it can legally cancel: a ticket already
``served`` (the kitchen finished and the food went out -- cancelling it
after the fact would misrepresent history) or already ``cancelled``
(nothing to do) is left untouched. Cascades down to every non-terminal
``KitchenItem`` on a ticket it does cancel, so the KDS never shows a
"cancelled" ticket card with a child item still reading
"in progress" -- see ``KitchenTicket.cancel()``/``KitchenItem.cancel()``
for the precondition each one enforces.

Publishes one ``KitchenTicketCancelled`` per ticket actually cancelled,
same "cascade helper owns its own event" shape ``_recipe_deduction.py``
already established for ``LowStockDetected``.
"""

from __future__ import annotations

from datetime import datetime

from restaurant_os_api.modules.operations.domain.entities import (
    KitchenItemStatus,
    KitchenTicketStatus,
)
from restaurant_os_api.modules.operations.domain.events import KitchenTicketCancelled
from restaurant_os_api.modules.operations.domain.ports import KitchenTicketRepository
from restaurant_os_api.platform.outbox import OutboxWriter

_ITEM_CANCELLABLE_FROM = (
    KitchenItemStatus.QUEUED,
    KitchenItemStatus.IN_PROGRESS,
    KitchenItemStatus.READY,
)


async def cancel_kitchen_tickets_for_order(
    *,
    tenant_id: str,
    order_id: str,
    now: datetime,
    kitchen_ticket_repo: KitchenTicketRepository,
    outbox: OutboxWriter,
) -> None:
    tickets = await kitchen_ticket_repo.list_for_order(tenant_id, order_id)
    for ticket in tickets:
        if ticket.status in (KitchenTicketStatus.SERVED, KitchenTicketStatus.CANCELLED):
            continue

        ticket.cancel(cancelled_at=now)
        await kitchen_ticket_repo.update(ticket)

        items = await kitchen_ticket_repo.get_items(tenant_id, ticket.id)
        for item in items:
            if item.status in _ITEM_CANCELLABLE_FROM:
                item.cancel()
                await kitchen_ticket_repo.update_item(item)

        await outbox.publish(
            tenant_id,
            KitchenTicketCancelled(kitchen_ticket_id=ticket.id, order_id=order_id, occurred_at=now),
        )
