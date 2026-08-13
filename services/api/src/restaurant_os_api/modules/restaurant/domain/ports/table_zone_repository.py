"""Repository port for TableZone."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import TableZone


class TableZoneRepository(Protocol):
    async def get_by_id(self, tenant_id: str, table_zone_id: str) -> TableZone | None: ...

    async def get_by_branch_id_and_name(
        self, tenant_id: str, branch_id: str, name: str
    ) -> TableZone | None:
        """Mirror of ``UNIQUE (branch_id, name)``."""
        ...

    async def create(self, table_zone: TableZone) -> TableZone: ...

    async def update(self, table_zone: TableZone) -> TableZone: ...

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[TableZone], int]: ...
