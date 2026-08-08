"""Repository port for Permission."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import Permission


class PermissionRepository(Protocol):
    async def get_by_code(self, code: str) -> Permission | None: ...

    async def list_active(self) -> list[Permission]:
        """The full active permission catalogue — no tenant scoping
        (RBAC Foundation Architecture SS4.2: pure platform reference
        data, same as ``currencies``)."""
        ...
