"""Repository port for SystemSetting."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import SystemSetting


class SystemSettingRepository(Protocol):
    async def list_for_tenant(self, tenant_id: str) -> list[SystemSetting]: ...

    async def get_by_key(self, tenant_id: str, key: str) -> SystemSetting | None: ...

    async def upsert(self, setting: SystemSetting) -> SystemSetting:
        """Create or replace the setting for ``(tenant_id, key)``.

        Settings are looked up and overwritten by their natural key, not
        their ULID — callers never need to know a setting's `id` to
        update it.
        """
        ...
