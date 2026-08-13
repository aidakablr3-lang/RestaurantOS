"""Shared station-fan-out helper: one ``KitchenTicket`` per distinct
station present in a batch of just-fired ``OrderItem``s.

Extracted from ``FireOrderUseCase`` (station routing, Sprint 7 gap fix)
so ``GuestSubmitOrderUseCase`` (guest ordering) can create the identical
fan-out without either use case calling the other's ``.execute()`` --
this codebase's established no-cross-use-case-calls convention. Callers
are responsible for their own order/item status transitions
(``order.fire()``, ``item.fire()``) and persistence before calling this
-- it only creates tickets and kitchen items for the items it's given.
"""

from __future__ import annotations

from datetime import datetime

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.domain.entities import (
    KitchenItem,
    KitchenItemStatus,
    KitchenTicket,
    KitchenTicketStatus,
    OrderItem,
)
from restaurant_os_api.modules.operations.domain.ports import KitchenTicketRepository
from restaurant_os_api.modules.restaurant.domain.ports import MenuItemRepository


async def fan_out_items_into_station_tickets(
    *,
    tenant_id: str,
    order_id: str,
    fireable_items: list[OrderItem],
    now: datetime,
    menu_item_repo: MenuItemRepository,
    kitchen_ticket_repo: KitchenTicketRepository,
) -> None:
    items_by_station: dict[str, list[OrderItem]] = {}
    for item in fireable_items:
        menu_item = await menu_item_repo.get_by_id(tenant_id, item.menu_item_id)
        station = menu_item.station.value if menu_item is not None else "kitchen"
        items_by_station.setdefault(station, []).append(item)

    for station, station_items in items_by_station.items():
        ticket = await kitchen_ticket_repo.create(
            KitchenTicket(
                id=generate_ulid(),
                tenant_id=tenant_id,
                order_id=order_id,
                station=station,
                status=KitchenTicketStatus.FIRED,
                created_at=now,
            )
        )
        for item in station_items:
            await kitchen_ticket_repo.add_item(
                KitchenItem(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    kitchen_ticket_id=ticket.id,
                    order_item_id=item.id,
                    status=KitchenItemStatus.QUEUED,
                    created_at=now,
                )
            )
