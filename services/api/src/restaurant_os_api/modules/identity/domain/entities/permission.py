"""Permission entity.

RBAC Foundation Architecture SS4.2: a single, granular, platform-defined
capability — never tenant-editable. No ``tenant_id`` at all (unlike
every other entity in this module): a permission code means the same
thing for every tenant, exactly like ``Currency``.

``code`` is the primary key (e.g. ``"branch.manage"``), a deliberate
deviation from the universal ULID-primary-key convention — mirrors the
one other precedent for a human-referenced, code-as-primary-key
reference table already in this schema, ``ChartOfAccount.account_code``
(Data Architecture v2.0 Group I), for the identical reason: permission
codes are referenced directly in application code
(``require_permission("branch.manage")``), not looked up by an opaque
generated id.
"""

from __future__ import annotations

from dataclasses import dataclass

from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidPermissionStateTransitionError,
)


@dataclass(slots=True)
class Permission:
    code: str
    module: str
    description: str
    is_active: bool = True

    def deactivate(self) -> None:
        if not self.is_active:
            raise InvalidPermissionStateTransitionError(self.code, "inactive", "inactive")
        self.is_active = False

    def activate(self) -> None:
        if self.is_active:
            raise InvalidPermissionStateTransitionError(self.code, "active", "active")
        self.is_active = True
