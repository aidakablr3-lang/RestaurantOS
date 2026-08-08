"""UserRole entity.

RBAC Foundation Architecture SS4.4: join table assigning a ``Role`` to a
``User``, optionally scoped to a specific ``Branch``. This is the
entity that makes a user holding a tenant-wide role *and* multiple
branch-specific roles simultaneously possible — one row per
(role, scope) pair, distinguished by ``branch_id``.

Revocation is soft-delete at the repository layer (Data Architecture
v1.0 SS3.1: "revocation recorded, not deleted, for audit of who had
what access when") — this entity carries no in-domain lifecycle state
machine of its own (unlike ``Tenant``/``User``, which have genuine
multi-state enums), so there is deliberately no ``revoke()`` method
here; the revoking use case calls the repository's own revoke
operation directly, the same way retiring a ``RolePermission`` grant
needs no entity-level method either.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class UserRole:
    id: str
    tenant_id: str
    user_id: str
    role_id: str
    branch_id: str | None
    granted_at: datetime
    granted_by_user_id: str | None

    @property
    def is_tenant_wide(self) -> bool:
        return self.branch_id is None
