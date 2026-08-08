"""Repository port for MenuCategory."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import MenuCategory


class MenuCategoryRepository(Protocol):
    async def get_by_id(self, tenant_id: str, menu_category_id: str) -> MenuCategory | None: ...

    async def get_by_restaurant_id_and_name(
        self, tenant_id: str, restaurant_id: str, name: str
    ) -> MenuCategory | None:
        """Mirror of ``UNIQUE (restaurant_id, name)``."""
        ...

    async def create(self, menu_category: MenuCategory) -> MenuCategory: ...

    async def update(self, menu_category: MenuCategory) -> MenuCategory: ...

    async def list_for_restaurant(
        self, tenant_id: str, restaurant_id: str, *, offset: int, limit: int
    ) -> tuple[list[MenuCategory], int]: ...
