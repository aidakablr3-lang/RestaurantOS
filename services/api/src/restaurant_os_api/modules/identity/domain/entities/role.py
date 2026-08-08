"""Role entity.

RBAC Foundation Architecture SS4.1: a named, grantable bundle of
permissions. ``tenant_id`` is nullable — ``NOT NULL`` for a tenant's own
roles (system-seeded defaults or tenant-custom roles), ``NULL`` for a
platform-wide role. No platform-wide ``Role`` row is created by this
pass (``is_platform_admin`` remains the sole platform-level mechanism,
RBAC Foundation Architecture SS10) — the nullable column exists so that
path stays open later without a schema change.

``default_scope`` is informational only (an authoring hint for the
future Roles & Permissions UI), never a structural constraint — a role
named "Branch Manager" is always granted branch-specifically in
practice, but nothing here *forces* that, since a ``CHECK`` constraint
cannot reference another table's row without a trigger, and this is a
UX judgment, not a data-integrity rule (RBAC Foundation Architecture
SS5.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidRoleLifecycleTransitionError,
)


class RoleScope(StrEnum):
    TENANT = "tenant"
    BRANCH = "branch"


@dataclass(slots=True)
class Role:
    id: str
    tenant_id: str | None
    name: str
    description: str | None
    default_scope: RoleScope
    is_system: bool
    is_active: bool
    created_at: datetime

    @property
    def is_platform_wide(self) -> bool:
        return self.tenant_id is None

    def deactivate(self) -> None:
        """Retire this role. Whether it is still actively granted to any
        user is a cross-aggregate question this entity cannot answer on
        its own (it has no visibility into ``UserRole`` rows) — that
        check belongs to the application-layer use case, which has a
        repository to ask."""
        if not self.is_active:
            raise InvalidRoleLifecycleTransitionError(self.id, "inactive", "inactive")
        self.is_active = False

    def activate(self) -> None:
        if self.is_active:
            raise InvalidRoleLifecycleTransitionError(self.id, "active", "active")
        self.is_active = True
