"""Repository port for PurchaseOrder -- bundles its PurchaseOrderItem
children, mirroring ``OrderRepository``'s own Order+OrderItem shape."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import PurchaseOrder, PurchaseOrderItem


class PurchaseOrderRepository(Protocol):
    async def get_by_id(self, tenant_id: str, purchase_order_id: str) -> PurchaseOrder | None: ...

    async def create(self, purchase_order: PurchaseOrder) -> PurchaseOrder: ...

    async def update(self, purchase_order: PurchaseOrder) -> PurchaseOrder: ...

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[PurchaseOrder], int]: ...

    async def get_items(
        self, tenant_id: str, purchase_order_id: str
    ) -> list[PurchaseOrderItem]: ...

    async def get_item_by_id(
        self, tenant_id: str, purchase_order_item_id: str
    ) -> PurchaseOrderItem | None: ...

    async def add_item(self, item: PurchaseOrderItem) -> PurchaseOrderItem: ...

    async def update_item(self, item: PurchaseOrderItem) -> PurchaseOrderItem: ...
