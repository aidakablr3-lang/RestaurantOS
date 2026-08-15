from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import KitchenItemDTO, KitchenTicketDTO
from restaurant_os_api.modules.operations.domain.entities import (
    KitchenItem,
    KitchenTicket,
    OrderItem,
)
from restaurant_os_api.modules.restaurant.domain.entities import MenuItem

_UNKNOWN_ITEM_NAME = "Unknown item"


def resolve_kitchen_item_identity(
    item: KitchenItem,
    *,
    order_items_by_id: dict[str, OrderItem],
    menu_items_by_id: dict[str, MenuItem],
) -> tuple[str, int]:
    """(menu_item_name, quantity) for a KitchenItem, so the KDS board can
    show what to actually cook/pour rather than a bare status badge --
    falls back to "Unknown item"/0 if the order item or menu item has
    since been deleted, matching ``get_end_of_day_report.py``'s own
    precedent for enriching an id with a name that might not resolve."""
    order_item = order_items_by_id.get(item.order_item_id)
    if order_item is None:
        return _UNKNOWN_ITEM_NAME, 0
    menu_item = menu_items_by_id.get(order_item.menu_item_id)
    name = menu_item.name if menu_item is not None else _UNKNOWN_ITEM_NAME
    return name, order_item.quantity


def kitchen_item_to_dto(item: KitchenItem, *, menu_item_name: str, quantity: int) -> KitchenItemDTO:
    return KitchenItemDTO(
        id=item.id,
        kitchen_ticket_id=item.kitchen_ticket_id,
        order_item_id=item.order_item_id,
        menu_item_name=menu_item_name,
        quantity=quantity,
        status=item.status.value,
        created_at=item.created_at,
    )


def kitchen_ticket_to_dto(ticket: KitchenTicket, items: list[KitchenItemDTO]) -> KitchenTicketDTO:
    return KitchenTicketDTO(
        id=ticket.id,
        tenant_id=ticket.tenant_id,
        order_id=ticket.order_id,
        station=ticket.station,
        status=ticket.status.value,
        created_at=ticket.created_at,
        items=items,
    )
