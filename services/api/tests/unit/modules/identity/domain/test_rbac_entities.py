"""Domain-level unit tests for the RBAC entities and RoleGrantPolicy.

RBAC Foundation Architecture SS4/SS16.1 (implemented in Commits 1 and
5). No database, no I/O -- pure entity/policy behavior, matching this
module's existing domain test style (test_tenant.py, test_user.py).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.domain.entities import (
    Permission,
    Role,
    RolePermission,
    RoleScope,
    UserRole,
)
from restaurant_os_api.modules.identity.domain.exceptions import (
    InsufficientGrantAuthorityError,
    InvalidPermissionStateTransitionError,
    InvalidRoleLifecycleTransitionError,
)
from restaurant_os_api.modules.identity.domain.services import RoleGrantPolicy

NOW = datetime.now(UTC)


def _role(*, tenant_id: str | None = "tenant-1", is_active: bool = True) -> Role:
    return Role(
        id="role-1",
        tenant_id=tenant_id,
        name="Branch Manager",
        description="Manages one branch.",
        default_scope=RoleScope.BRANCH,
        is_system=True,
        is_active=is_active,
        created_at=NOW,
    )


def _permission(code: str = "menu.read", *, is_active: bool = True) -> Permission:
    return Permission(code=code, module="restaurant", description="desc", is_active=is_active)


class TestRoleLifecycle:
    def test_a_freshly_created_role_is_active(self) -> None:
        role = _role()
        assert role.is_active is True

    def test_deactivate_retires_an_active_role(self) -> None:
        role = _role()
        role.deactivate()
        assert role.is_active is False

    def test_deactivate_twice_raises(self) -> None:
        role = _role(is_active=False)
        with pytest.raises(InvalidRoleLifecycleTransitionError):
            role.deactivate()

    def test_activate_reinstates_a_retired_role(self) -> None:
        role = _role(is_active=False)
        role.activate()
        assert role.is_active is True

    def test_activate_an_already_active_role_raises(self) -> None:
        role = _role()
        with pytest.raises(InvalidRoleLifecycleTransitionError):
            role.activate()

    def test_is_platform_wide_true_only_when_tenant_id_is_none(self) -> None:
        assert _role(tenant_id=None).is_platform_wide is True
        assert _role(tenant_id="tenant-1").is_platform_wide is False

    def test_tenant_scoped_role_reports_scope_correctly(self) -> None:
        role = _role(tenant_id="tenant-1")
        assert role.tenant_id == "tenant-1"
        assert role.is_platform_wide is False


class TestPermissionLifecycle:
    def test_a_freshly_created_permission_defaults_active(self) -> None:
        assert _permission().is_active is True

    def test_deactivate_retires_a_permission(self) -> None:
        permission = _permission()
        permission.deactivate()
        assert permission.is_active is False

    def test_deactivate_twice_raises(self) -> None:
        permission = _permission(is_active=False)
        with pytest.raises(InvalidPermissionStateTransitionError):
            permission.deactivate()

    def test_activate_reinstates_a_retired_permission(self) -> None:
        permission = _permission(is_active=False)
        permission.activate()
        assert permission.is_active is True

    def test_activate_an_already_active_permission_raises(self) -> None:
        permission = _permission()
        with pytest.raises(InvalidPermissionStateTransitionError):
            permission.activate()


class TestRolePermissionAndUserRoleShape:
    def test_role_permission_is_a_thin_association_with_no_behavior(self) -> None:
        rp = RolePermission(
            id="rp-1", role_id="role-1", permission_code="menu.read", created_at=NOW
        )
        assert rp.role_id == "role-1"
        assert rp.permission_code == "menu.read"

    def test_user_role_is_tenant_wide_when_branch_id_is_none(self) -> None:
        ur = UserRole(
            id="ur-1",
            tenant_id="tenant-1",
            user_id="user-1",
            role_id="role-1",
            branch_id=None,
            granted_at=NOW,
            granted_by_user_id="granter-1",
        )
        assert ur.is_tenant_wide is True

    def test_user_role_is_not_tenant_wide_when_branch_id_is_set(self) -> None:
        ur = UserRole(
            id="ur-2",
            tenant_id="tenant-1",
            user_id="user-1",
            role_id="role-1",
            branch_id="branch-a",
            granted_at=NOW,
            granted_by_user_id="granter-1",
        )
        assert ur.is_tenant_wide is False


class TestRoleGrantPolicyDelegationCeiling:
    def test_delegating_a_subset_of_held_permissions_is_allowed(self) -> None:
        RoleGrantPolicy.ensure_can_delegate(
            actor_permission_codes=frozenset({"menu.read", "menu.manage", "table.read"}),
            permission_codes_to_delegate=frozenset({"menu.read"}),
        )  # must not raise

    def test_delegating_a_permission_the_actor_lacks_raises(self) -> None:
        with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
            RoleGrantPolicy.ensure_can_delegate(
                actor_permission_codes=frozenset({"menu.read"}),
                permission_codes_to_delegate=frozenset({"menu.manage"}),
            )
        assert exc_info.value.reason == "delegation"

    def test_delegating_zero_permissions_is_always_allowed(self) -> None:
        RoleGrantPolicy.ensure_can_delegate(
            actor_permission_codes=frozenset(),
            permission_codes_to_delegate=frozenset(),
        )  # must not raise


class TestRoleGrantPolicyScopeCeiling:
    def test_tenant_wide_assign_covers_any_branch(self) -> None:
        RoleGrantPolicy.ensure_scope_covered(
            actor_has_tenant_wide_assign=True,
            actor_branch_ids_with_assign=frozenset(),
            target_branch_id="branch-a",
            action="grant",
        )  # must not raise

    def test_tenant_wide_assign_covers_a_tenant_wide_target(self) -> None:
        RoleGrantPolicy.ensure_scope_covered(
            actor_has_tenant_wide_assign=True,
            actor_branch_ids_with_assign=frozenset(),
            target_branch_id=None,
            action="grant",
        )  # must not raise

    def test_branch_scoped_assign_covers_only_that_exact_branch(self) -> None:
        RoleGrantPolicy.ensure_scope_covered(
            actor_has_tenant_wide_assign=False,
            actor_branch_ids_with_assign=frozenset({"branch-a"}),
            target_branch_id="branch-a",
            action="grant",
        )  # must not raise

    def test_branch_scoped_assign_never_covers_a_tenant_wide_target(self) -> None:
        with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
            RoleGrantPolicy.ensure_scope_covered(
                actor_has_tenant_wide_assign=False,
                actor_branch_ids_with_assign=frozenset({"branch-a"}),
                target_branch_id=None,
                action="grant",
            )
        assert exc_info.value.reason == "scope"

    def test_branch_scoped_assign_never_covers_a_different_branch(self) -> None:
        with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
            RoleGrantPolicy.ensure_scope_covered(
                actor_has_tenant_wide_assign=False,
                actor_branch_ids_with_assign=frozenset({"branch-a"}),
                target_branch_id="branch-b",
                action="grant",
            )
        assert exc_info.value.reason == "scope"

    def test_no_assign_authority_at_all_is_always_denied(self) -> None:
        with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
            RoleGrantPolicy.ensure_scope_covered(
                actor_has_tenant_wide_assign=False,
                actor_branch_ids_with_assign=frozenset(),
                target_branch_id="branch-a",
                action="grant",
            )
        assert exc_info.value.reason == "scope"


class TestRoleGrantPolicyEnsureCanGrant:
    def test_scope_is_checked_before_delegation(self) -> None:
        """Both ceilings fail here; the error raised must be the scope
        one -- ensure_can_grant's own docstring states scope is checked
        first."""
        role = _role()
        with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
            RoleGrantPolicy.ensure_can_grant(
                granter_has_tenant_wide_assign=False,
                granter_branch_ids_with_assign=frozenset(),
                granter_permission_codes=frozenset(),
                target_role=role,
                target_role_permission_codes=frozenset({"menu.manage"}),
                target_branch_id="branch-a",
            )
        assert exc_info.value.reason == "scope"

    def test_scope_ok_but_delegation_fails_raises_delegation_error(self) -> None:
        role = _role()
        with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
            RoleGrantPolicy.ensure_can_grant(
                granter_has_tenant_wide_assign=True,
                granter_branch_ids_with_assign=frozenset(),
                granter_permission_codes=frozenset({"roles.assign"}),
                target_role=role,
                target_role_permission_codes=frozenset({"menu.manage"}),
                target_branch_id="branch-a",
            )
        assert exc_info.value.reason == "delegation"

    def test_both_ceilings_satisfied_allows_the_grant(self) -> None:
        role = _role()
        RoleGrantPolicy.ensure_can_grant(
            granter_has_tenant_wide_assign=True,
            granter_branch_ids_with_assign=frozenset(),
            granter_permission_codes=frozenset({"roles.assign", "menu.manage"}),
            target_role=role,
            target_role_permission_codes=frozenset({"menu.manage"}),
            target_branch_id="branch-a",
        )  # must not raise


class TestRoleGrantPolicyEnsureCanRevoke:
    def test_revoke_has_no_delegation_ceiling(self) -> None:
        """A revoker holding roles.assign at the right scope but zero
        other permissions can still revoke -- revoking hands out
        nothing new, so there is nothing to delegate-check."""
        RoleGrantPolicy.ensure_can_revoke(
            revoker_has_tenant_wide_assign=False,
            revoker_branch_ids_with_assign=frozenset({"branch-a"}),
            target_branch_id="branch-a",
        )  # must not raise

    def test_revoke_still_enforces_the_scope_ceiling(self) -> None:
        with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
            RoleGrantPolicy.ensure_can_revoke(
                revoker_has_tenant_wide_assign=False,
                revoker_branch_ids_with_assign=frozenset({"branch-a"}),
                target_branch_id="branch-b",
            )
        assert exc_info.value.reason == "scope"
