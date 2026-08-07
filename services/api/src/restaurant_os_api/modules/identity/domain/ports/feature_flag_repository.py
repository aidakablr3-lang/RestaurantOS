"""Repository port for FeatureFlag."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import FeatureFlag


class FeatureFlagRepository(Protocol):
    async def list_effective_for_tenant(self, tenant_id: str) -> list[FeatureFlag]:
        """Return every flag visible to ``tenant_id``: that tenant's own
        flags plus every platform-wide flag (``tenant_id IS NULL``).

        "Visible" is not the same as "on" — callers still evaluate
        ``FeatureFlag.is_effective_for()`` per flag; this method only
        resolves *which* flags apply.
        """
        ...

    async def get_by_key(self, tenant_id: str, key: str) -> FeatureFlag | None:
        """Look up one flag by key, preferring a tenant-specific override
        over the platform-wide default of the same key."""
        ...

    async def create(self, flag: FeatureFlag) -> FeatureFlag: ...
