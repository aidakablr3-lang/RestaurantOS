"""Repository port for the Order aggregate (Order + its OrderItem
children)."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import Order, OrderItem


class OrderRepository(Protocol):
    async def get_by_id(self, tenant_id: str, order_id: str) -> Order | None: ...

    async def create(self, order: Order) -> Order: ...

    async def update(self, order: Order) -> Order: ...

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[Order], int]: ...

    async def get_items(self, tenant_id: str, order_id: str) -> list[OrderItem]: ...

    async def get_item_by_id(self, tenant_id: str, order_item_id: str) -> OrderItem | None: ...

    async def add_item(self, item: OrderItem) -> OrderItem: ...

    async def update_item(self, item: OrderItem) -> OrderItem: ...
