"""Repository port for InventoryItem."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import InventoryItem


class InventoryItemRepository(Protocol):
    async def get_by_id(self, tenant_id: str, inventory_item_id: str) -> InventoryItem | None: ...

    async def create(self, item: InventoryItem) -> InventoryItem: ...

    async def update(self, item: InventoryItem) -> InventoryItem: ...

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[InventoryItem], int]: ...

    async def get_by_branch_id_and_name(
        self, tenant_id: str, branch_id: str, name: str
    ) -> InventoryItem | None: ...
