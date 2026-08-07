"""Repository port for TenantDirectoryEntry."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import TenantDirectoryEntry


class TenantDirectoryRepository(Protocol):
    async def get_by_tenant_id(self, tenant_id: str) -> TenantDirectoryEntry | None: ...

    async def create(self, entry: TenantDirectoryEntry) -> TenantDirectoryEntry: ...

    async def update_status(self, tenant_id: str, status: str) -> None:
        """Mirror a tenant's lifecycle status into its directory entry.

        Kept in sync by the same lifecycle use cases that change
        ``tenants.status`` (Data Architecture v2.0 SS4.4) — the directory
        is a routing cache derived from the tenant, never an independent
        source of truth for status.
        """
        ...
