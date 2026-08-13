from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import MenuItemDTO
from restaurant_os_api.modules.restaurant.domain.entities import MenuItem


def menu_item_to_dto(menu_item: MenuItem) -> MenuItemDTO:
    return MenuItemDTO(
        id=menu_item.id,
        tenant_id=menu_item.tenant_id,
        menu_category_id=menu_item.menu_category_id,
        name=menu_item.name,
        price_amount=menu_item.price_amount,
        currency_code=menu_item.currency_code,
        is_available=menu_item.is_available,
        display_order=menu_item.display_order,
        recipe_id=menu_item.recipe_id,
        created_at=menu_item.created_at,
        station=menu_item.station.value,
    )
