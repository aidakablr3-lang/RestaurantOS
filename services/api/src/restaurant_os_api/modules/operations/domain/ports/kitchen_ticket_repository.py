"""Repository port for the KitchenTicket aggregate (KitchenTicket + its
KitchenItem children)."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import KitchenItem, KitchenTicket


class KitchenTicketRepository(Protocol):
    async def get_by_id(self, tenant_id: str, kitchen_ticket_id: str) -> KitchenTicket | None: ...

    async def create(self, ticket: KitchenTicket) -> KitchenTicket: ...

    async def update(self, ticket: KitchenTicket) -> KitchenTicket: ...

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[KitchenTicket], int]:
        """Joins through ``orders`` -- ``kitchen_tickets`` carries no
        ``branch_id`` column of its own (Architecture doc SS9)."""
        ...

    async def get_items(self, tenant_id: str, kitchen_ticket_id: str) -> list[KitchenItem]: ...

    async def get_item_by_id(self, tenant_id: str, kitchen_item_id: str) -> KitchenItem | None: ...

    async def add_item(self, item: KitchenItem) -> KitchenItem: ...

    async def update_item(self, item: KitchenItem) -> KitchenItem: ...
