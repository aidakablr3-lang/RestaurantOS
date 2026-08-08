"""RoleGrantPolicy — the privilege-escalation rule as pure domain logic.

RBAC Foundation Architecture SS16.1/SS18: "a granter can only issue a
UserRole grant at a scope at or below their own highest held scope...
and must never be able to grant a permission they don't themselves
hold." This is a rule that spans two aggregates (the granter's own
resolved roles/permissions, and the role being granted) and therefore
does not belong on any single entity — a new ``domain/services/``
package is introduced specifically for this shape of rule (a stateless
domain operation, no I/O, not naturally owned by one entity), distinct
from ``application/services/`` (``TenantProvisioningService``'s home),
which is reserved for orchestration that *does* perform I/O.

Pure logic only: every input here is already-loaded data. The calling
use case (``AssignUserRoleUseCase``, Commit 5) is responsible for
resolving the granter's own permission/scope set via the repositories
before calling this, and for persisting the grant afterward.
"""

from __future__ import annotations

from restaurant_os_api.modules.identity.domain.entities.role import Role
from restaurant_os_api.modules.identity.domain.exceptions import InsufficientGrantAuthorityError


class RoleGrantPolicy:
    @staticmethod
    def ensure_can_grant(
        *,
        granter_has_tenant_wide_assign: bool,
        granter_branch_ids_with_assign: frozenset[str],
        granter_permission_codes: frozenset[str],
        target_role: Role,
        target_role_permission_codes: frozenset[str],
        target_branch_id: str | None,
    ) -> None:
        """Raise ``InsufficientGrantAuthorityError`` if the granter may
        not issue this grant. Two independent ceilings, both checked:

        1. Scope ceiling — the requested grant's scope must be covered
           by the granter's own ``roles.assign`` scope. A tenant-wide
           ``roles.assign`` covers any branch; a branch-scoped one only
           covers that exact branch, never a tenant-wide grant.
        2. Delegation ceiling — every permission the target role
           carries must already be held by the granter. A granter
           cannot hand out access they don't have themselves,
           regardless of their own scope.
        """
        scope_ok = granter_has_tenant_wide_assign or (
            target_branch_id is not None and target_branch_id in granter_branch_ids_with_assign
        )
        if not scope_ok:
            raise InsufficientGrantAuthorityError(
                reason="scope",
                detail=(
                    f"Cannot grant role '{target_role.id}' at "
                    f"{'tenant-wide' if target_branch_id is None else f'branch {target_branch_id!r}'} "
                    "scope — exceeds the caller's own roles.assign scope."
                ),
            )

        undelegatable = target_role_permission_codes - granter_permission_codes
        if undelegatable:
            raise InsufficientGrantAuthorityError(
                reason="delegation",
                detail=(
                    f"Cannot grant role '{target_role.id}' — it carries permissions the "
                    f"caller does not hold: {sorted(undelegatable)}"
                ),
            )
