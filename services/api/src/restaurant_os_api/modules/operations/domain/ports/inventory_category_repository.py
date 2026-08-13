"""Repository port for InventoryCategory."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import InventoryCategory


class InventoryCategoryRepository(Protocol):
    async def get_by_id(
        self, tenant_id: str, inventory_category_id: str
    ) -> InventoryCategory | None: ...

    async def create(self, category: InventoryCategory) -> InventoryCategory: ...

    async def list_for_tenant(self, tenant_id: str) -> list[InventoryCategory]: ...

    async def get_by_tenant_id_and_name(
        self, tenant_id: str, name: str
    ) -> InventoryCategory | None: ...
