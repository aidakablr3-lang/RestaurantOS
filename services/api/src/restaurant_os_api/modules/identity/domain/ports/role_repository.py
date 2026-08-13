"""Repository port for Role."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import Role


class RoleRepository(Protocol):
    async def get_by_id(self, tenant_id: str, role_id: str) -> Role | None:
        """Look up a role by id, visible if it belongs to ``tenant_id``
        or is platform-wide (``tenant_id IS NULL``) — mirrors the
        table's own RLS predicate exactly (RBAC Foundation Architecture
        SS14.2), applied again here at the application layer as the
        belt-and-suspenders defense-in-depth every other repository in
        this module already practices."""
        ...

    async def get_by_name(self, tenant_id: str, name: str) -> Role | None: ...

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Role], int]:
        """Returns (roles, total_count). Includes platform-wide roles
        alongside the tenant's own, same visibility rule as
        ``get_by_id``."""
        ...

    async def create(self, role: Role) -> Role: ...

    async def update(self, role: Role) -> Role: ...
