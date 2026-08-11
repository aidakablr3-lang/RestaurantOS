"""Repository port for LedgerEntry -- append-only, written once."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import LedgerEntry


class LedgerRepository(Protocol):
    async def add(self, entry: LedgerEntry) -> LedgerEntry: ...

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[LedgerEntry], int]: ...
