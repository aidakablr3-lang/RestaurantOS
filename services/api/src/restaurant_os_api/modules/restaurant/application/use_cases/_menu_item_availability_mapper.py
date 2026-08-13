from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import MenuItemAvailabilityDTO
from restaurant_os_api.modules.restaurant.domain.entities import MenuItemAvailability


def menu_item_availability_to_dto(row: MenuItemAvailability) -> MenuItemAvailabilityDTO:
    return MenuItemAvailabilityDTO(
        id=row.id,
        tenant_id=row.tenant_id,
        branch_id=row.branch_id,
        menu_item_id=row.menu_item_id,
        is_available=row.is_available,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        created_at=row.created_at,
    )
