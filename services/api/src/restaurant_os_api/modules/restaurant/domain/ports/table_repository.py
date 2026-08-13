"""Repository port for Table."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import Table


class TableRepository(Protocol):
    async def get_by_id(self, tenant_id: str, table_id: str) -> Table | None: ...

    async def get_by_branch_id_and_table_number(
        self, tenant_id: str, branch_id: str, table_number: str
    ) -> Table | None:
        """Mirror of ``UNIQUE (branch_id, table_number)``."""
        ...

    async def create(self, table: Table) -> Table: ...

    async def update(self, table: Table) -> Table:
        """Persists every mutable field, including ``status`` and
        ``sync_version`` -- callers own the optimistic-concurrency
        check (``sync_version``, Restaurant Platform Architecture SS9.2)
        before calling this; the repository does not enforce it itself
        at the data-layer this step (Step 4's use case does)."""
        ...

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[Table], int]: ...

    async def list_for_table_zone(self, tenant_id: str, table_zone_id: str) -> list[Table]: ...
