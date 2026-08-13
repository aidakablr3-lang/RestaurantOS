"""Repository port for MenuItemAvailability."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import MenuItemAvailability


class MenuItemAvailabilityRepository(Protocol):
    async def get_by_id(self, tenant_id: str, row_id: str) -> MenuItemAvailability | None: ...

    async def create(self, row: MenuItemAvailability) -> MenuItemAvailability: ...

    async def list_for_menu_item(
        self, tenant_id: str, menu_item_id: str
    ) -> list[MenuItemAvailability]: ...
