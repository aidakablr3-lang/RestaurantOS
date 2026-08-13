"""Repository port for the Order aggregate (Order + its OrderItem
children)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import Order, OrderItem


class OrderRepository(Protocol):
    async def get_by_id(self, tenant_id: str, order_id: str) -> Order | None: ...

    async def create(self, order: Order) -> Order: ...

    async def update(self, order: Order) -> Order: ...

    async def list_for_branch(
        self,
        tenant_id: str,
        branch_id: str,
        *,
        offset: int,
        limit: int,
        table_id: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Order], int]: ...

    async def list_for_branch_opened_between(
        self, tenant_id: str, branch_id: str, start: datetime, end: datetime
    ) -> list[Order]: ...

    async def list_items_for_orders(
        self, tenant_id: str, order_ids: list[str]
    ) -> list[OrderItem]: ...

    async def count_items_for_orders(
        self, tenant_id: str, order_ids: list[str]
    ) -> dict[str, int]: ...

    async def get_items(self, tenant_id: str, order_id: str) -> list[OrderItem]: ...

    async def get_item_by_id(self, tenant_id: str, order_item_id: str) -> OrderItem | None: ...

    async def add_item(self, item: OrderItem) -> OrderItem: ...

    async def update_item(self, item: OrderItem) -> OrderItem: ...
