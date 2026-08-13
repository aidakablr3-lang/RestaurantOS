from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import MenuCategoryDTO
from restaurant_os_api.modules.restaurant.domain.entities import MenuCategory


def menu_category_to_dto(menu_category: MenuCategory) -> MenuCategoryDTO:
    return MenuCategoryDTO(
        id=menu_category.id,
        tenant_id=menu_category.tenant_id,
        restaurant_id=menu_category.restaurant_id,
        name=menu_category.name,
        display_order=menu_category.display_order,
        created_at=menu_category.created_at,
    )
