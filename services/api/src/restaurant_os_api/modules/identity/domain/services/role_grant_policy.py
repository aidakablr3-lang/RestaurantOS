"""RoleGrantPolicy — the privilege-escalation rules as pure domain logic.

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
use case (``AssignUserRoleUseCase``/``RevokeUserRoleUseCase``, Commit 5;
``CreateRoleUseCase``/``UpdateRolePermissionsUseCase``, Commit 6) is
responsible for resolving the acting user's own permission/scope set
via the repositories before calling this, and for persisting the
result afterward.

Structural note on Platform Admin: nothing in this module, or anywhere
else RBAC touches, ever reads or writes ``users.is_platform_admin`` —
"assign Platform Admin privileges" via RBAC is not a case this policy
needs to guard against by special-casing a role name, because no RBAC
code path can reach that column at all (RBAC Foundation Architecture
SS10.2). Proven by a dedicated test (Commit 8), not by defensive code
here for a scenario the type system and the module boundary already
make impossible.
"""

from __future__ import annotations

from restaurant_os_api.modules.identity.domain.entities.role import Role
from restaurant_os_api.modules.identity.domain.exceptions import InsufficientGrantAuthorityError


class RoleGrantPolicy:
    @staticmethod
    def ensure_can_delegate(
        *, actor_permission_codes: frozenset[str], permission_codes_to_delegate: frozenset[str]
    ) -> None:
        """The delegation ceiling alone: every code in
        ``permission_codes_to_delegate`` must already be held by the
        actor. Reused by both the grant-to-user path (below) and role
        authoring itself (``CreateRoleUseCase``/
        ``UpdateRolePermissionsUseCase``, Commit 6) — a user must not be
        able to define a *new* role carrying permissions they don't
        hold, any more than they can hand out an *existing* one."""
        undelegatable = permission_codes_to_delegate - actor_permission_codes
        if undelegatable:
            raise InsufficientGrantAuthorityError(
                reason="delegation",
                detail=(
                    f"Cannot delegate permissions the caller does not hold: {sorted(undelegatable)}"
                ),
            )

    @staticmethod
    def ensure_scope_covered(
        *,
        actor_has_tenant_wide_assign: bool,
        actor_branch_ids_with_assign: frozenset[str],
        target_branch_id: str | None,
        action: str,
    ) -> None:
        """The scope ceiling alone: the target scope must be covered by
        the actor's own ``roles.assign`` scope. A tenant-wide
        ``roles.assign`` covers every branch; a branch-scoped one only
        covers that exact branch, never a tenant-wide action. Shared by
        both granting and revoking (RBAC Foundation Architecture SS16.1
        names granting explicitly; revocation is symmetric — a caller
        must not be able to revoke access at a branch they have no
        authority over, any more than they could grant it there)."""
        scope_ok = actor_has_tenant_wide_assign or (
            target_branch_id is not None and target_branch_id in actor_branch_ids_with_assign
        )
        if not scope_ok:
            raise InsufficientGrantAuthorityError(
                reason="scope",
                detail=(
                    f"Cannot {action} at "
                    f"{'tenant-wide' if target_branch_id is None else f'branch {target_branch_id!r}'} "
                    "scope — exceeds the caller's own roles.assign scope."
                ),
            )

    @classmethod
    def ensure_can_grant(
        cls,
        *,
        granter_has_tenant_wide_assign: bool,
        granter_branch_ids_with_assign: frozenset[str],
        granter_permission_codes: frozenset[str],
        target_role: Role,
        target_role_permission_codes: frozenset[str],
        target_branch_id: str | None,
    ) -> None:
        """Raise ``InsufficientGrantAuthorityError`` if the granter may
        not issue this grant. Two independent ceilings, both checked —
        scope first (cheaper, and the more common failure), then
        delegation."""
        cls.ensure_scope_covered(
            actor_has_tenant_wide_assign=granter_has_tenant_wide_assign,
            actor_branch_ids_with_assign=granter_branch_ids_with_assign,
            target_branch_id=target_branch_id,
            action=f"grant role '{target_role.id}'",
        )
        cls.ensure_can_delegate(
            actor_permission_codes=granter_permission_codes,
            permission_codes_to_delegate=target_role_permission_codes,
        )

    @classmethod
    def ensure_can_revoke(
        cls,
        *,
        revoker_has_tenant_wide_assign: bool,
        revoker_branch_ids_with_assign: frozenset[str],
        target_branch_id: str | None,
    ) -> None:
        """Scope ceiling only — revoking hands out nothing new, so
        there is no delegation ceiling to check, only "does the revoker
        have authority over this scope at all."""
        cls.ensure_scope_covered(
            actor_has_tenant_wide_assign=revoker_has_tenant_wide_assign,
            actor_branch_ids_with_assign=revoker_branch_ids_with_assign,
            target_branch_id=target_branch_id,
            action="revoke this role assignment",
        )
