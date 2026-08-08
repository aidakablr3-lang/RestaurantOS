"""Repository port for Branch."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import Branch


class BranchRepository(Protocol):
    async def get_by_id(self, tenant_id: str, branch_id: str) -> Branch | None: ...

    async def get_by_restaurant_id_and_name(
        self, tenant_id: str, restaurant_id: str, name: str
    ) -> Branch | None:
        """Application-layer mirror of ``UNIQUE (restaurant_id, name)`` --
        checked proactively before an insert, the constraint remains the
        actual guarantee under a race (same pattern as
        ``RoleRepository.get_by_name``)."""
        ...

    async def create(self, branch: Branch) -> Branch: ...

    async def update(self, branch: Branch) -> Branch: ...

    async def list_for_restaurant(
        self, tenant_id: str, restaurant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Branch], int]: ...
