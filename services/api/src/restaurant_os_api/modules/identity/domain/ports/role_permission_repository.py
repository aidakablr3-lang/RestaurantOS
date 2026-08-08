"""Repository port for RolePermission."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import RolePermission


class RolePermissionRepository(Protocol):
    async def list_permission_codes_for_role(self, role_id: str) -> frozenset[str]:
        """Only *active* permission codes (Permission.is_active = true)
        are returned — RBAC Foundation Architecture SS4.2: deactivating
        a Permission retires it from effective resolution immediately,
        even if a stale RolePermission row still references it."""
        ...

    async def add(self, role_permission: RolePermission) -> RolePermission: ...

    async def remove(self, role_id: str, permission_code: str) -> None: ...

    async def replace_for_role(self, role_id: str, permission_codes: frozenset[str]) -> None:
        """Atomically replace a role's full permission set — backs the
        ``PUT /roles/{id}/permissions`` endpoint (RBAC Foundation
        Architecture SS16), which replaces rather than incrementally
        patches."""
        ...
