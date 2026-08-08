"""Repository port for MenuItem."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import MenuItem


class MenuItemRepository(Protocol):
    async def get_by_id(self, tenant_id: str, menu_item_id: str) -> MenuItem | None: ...

    async def create(self, menu_item: MenuItem) -> MenuItem: ...

    async def update(self, menu_item: MenuItem) -> MenuItem: ...

    async def list_for_category(
        self, tenant_id: str, menu_category_id: str, *, offset: int, limit: int
    ) -> tuple[list[MenuItem], int]: ...
