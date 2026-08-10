from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import KitchenItemDTO, KitchenTicketDTO
from restaurant_os_api.modules.operations.domain.entities import KitchenItem, KitchenTicket


def kitchen_item_to_dto(item: KitchenItem) -> KitchenItemDTO:
    return KitchenItemDTO(
        id=item.id,
        kitchen_ticket_id=item.kitchen_ticket_id,
        order_item_id=item.order_item_id,
        status=item.status.value,
        created_at=item.created_at,
    )


def kitchen_ticket_to_dto(ticket: KitchenTicket, items: list[KitchenItem]) -> KitchenTicketDTO:
    return KitchenTicketDTO(
        id=ticket.id,
        tenant_id=ticket.tenant_id,
        order_id=ticket.order_id,
        station=ticket.station,
        status=ticket.status.value,
        created_at=ticket.created_at,
        items=[kitchen_item_to_dto(item) for item in items],
    )
