"""Application-layer DTOs for RBAC.

RBAC Foundation Architecture SS8: ``ResolvedPermissions`` is the
per-request output of permission resolution — server-computed, never
trusted from the client, never embedded in a JWT (SS8.2). It is the
one object the authorization service (Commit 4), the privilege-
escalation guard (Commit 5), and the ``GET /me/permissions`` endpoint
(Commit 6) all consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ResolvedPermissions:
    """A user's effective permissions, aggregated across every active
    role grant they hold (RBAC Foundation Architecture SS8): tenant-wide
    grants apply everywhere; branch-specific grants apply only within
    that branch. A permission held tenant-wide always satisfies a
    branch-scoped check too — the reverse is never true.
    """

    tenant_wide: frozenset[str] = field(default_factory=frozenset)
    by_branch: dict[str, frozenset[str]] = field(default_factory=dict)

    def has(self, code: str, *, branch_id: str | None = None) -> bool:
        if code in self.tenant_wide:
            return True
        if branch_id is not None:
            return code in self.by_branch.get(branch_id, frozenset())
        return False

    def branch_ids_with(self, code: str) -> frozenset[str]:
        """Every branch at which this specific code is held (not
        counting a tenant-wide grant, which already covers all
        branches) — the exact shape ``RoleGrantPolicy``'s
        ``granter_branch_ids_with_assign`` argument needs."""
        return frozenset(branch_id for branch_id, codes in self.by_branch.items() if code in codes)

    @property
    def all_codes(self) -> frozenset[str]:
        """Every permission code held at any scope — the exact shape
        ``RoleGrantPolicy``'s ``granter_permission_codes`` argument
        needs for the delegation-ceiling check."""
        result: set[str] = set(self.tenant_wide)
        for codes in self.by_branch.values():
            result |= codes
        return frozenset(result)


@dataclass(frozen=True, slots=True)
class RoleDTO:
    id: str
    tenant_id: str | None
    name: str
    description: str | None
    default_scope: str
    is_system: bool
    is_active: bool


@dataclass(frozen=True, slots=True)
class UserRoleDTO:
    id: str
    tenant_id: str
    user_id: str
    role_id: str
    branch_id: str | None
    granted_at: str
    granted_by_user_id: str | None


@dataclass(frozen=True, slots=True)
class AssignUserRoleRequestDTO:
    granter_user_id: str
    target_user_id: str
    role_id: str
    branch_id: str | None = None


@dataclass(frozen=True, slots=True)
class RevokeUserRoleRequestDTO:
    revoker_user_id: str
    user_role_id: str


@dataclass(frozen=True, slots=True)
class CreateRoleRequestDTO:
    creator_user_id: str
    name: str
    description: str | None
    default_scope: str
    permission_codes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ReplaceRolePermissionsRequestDTO:
    actor_user_id: str
    role_id: str
    permission_codes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class RoleListResultDTO:
    roles: list[RoleDTO]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class PermissionDTO:
    code: str
    module: str
    description: str
    is_active: bool
