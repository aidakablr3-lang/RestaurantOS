"""Repository port for UserRole."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import UserRole


class UserRoleRepository(Protocol):
    async def get_by_id(self, tenant_id: str, user_role_id: str) -> UserRole | None: ...

    async def list_active_for_user(self, tenant_id: str, user_id: str) -> list[UserRole]:
        """Every non-revoked grant a user holds, tenant-wide and
        branch-specific alike — the raw input to permission resolution
        (RBAC Foundation Architecture SS8)."""
        ...

    async def exists(
        self, tenant_id: str, user_id: str, role_id: str, branch_id: str | None
    ) -> bool:
        """Application-layer mirror of the database's own
        ``UNIQUE NULLS NOT DISTINCT (user_id, role_id, branch_id)``
        constraint (RBAC Foundation Architecture SS13.3) — checked
        proactively so a duplicate grant raises a clean domain error
        before ever reaching Postgres, in the common case; the
        constraint itself remains the actual guarantee for the rare
        race the proactive check can't catch."""
        ...

    async def create(self, user_role: UserRole) -> UserRole: ...

    async def revoke(self, tenant_id: str, user_role_id: str) -> UserRole | None:
        """Soft-deletes the grant (``deleted_at``) — revocation is
        recorded, never hard-deleted, for audit of who had what access
        when (Data Architecture v1.0 SS3.1). Returns the revoked row
        (for the caller to read ``user_id``/``role_id``/``branch_id``
        off, e.g. to bump ``permission_version`` and emit the
        ``UserRoleRevoked`` event), or ``None`` if no such active grant
        existed."""
        ...
