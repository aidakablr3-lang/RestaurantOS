"""Repository port for MenuItemBranchPrice."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import MenuItemBranchPrice


class MenuItemBranchPriceRepository(Protocol):
    async def get_by_id(self, tenant_id: str, row_id: str) -> MenuItemBranchPrice | None: ...

    async def create(self, row: MenuItemBranchPrice) -> MenuItemBranchPrice: ...

    async def list_for_menu_item(
        self, tenant_id: str, menu_item_id: str
    ) -> list[MenuItemBranchPrice]:
        """Every override window, historical and current -- resolving
        which one is currently effective is a Step 4 use-case concern,
        not this repository's."""
        ...
