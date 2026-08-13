"""Unit tests for ResolveUserPermissionsUseCase (RBAC Foundation
Architecture SS8) -- the single permission-aggregation algorithm every
authorization and privilege-escalation check depends on. All I/O is
faked; see tests/unit/modules/identity/fakes.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

from restaurant_os_api.modules.identity.application.use_cases import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import Role, RoleScope, UserRole
from tests.unit.modules.identity.fakes import (
    InMemoryRolePermissionRepository,
    InMemoryRoleRepository,
    InMemoryUserRoleRepository,
)
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID, USER_ID

NOW = datetime.now(UTC)
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAZ"
BRANCH_A = "01ARZ3NDEKTSV4RRFFQ6BRNCHA"
BRANCH_B = "01ARZ3NDEKTSV4RRFFQ6BRNCHB"


def _make_use_case(
    session_factory, role_repo, role_permission_repo, user_role_repo
) -> ResolveUserPermissionsUseCase:
    return ResolveUserPermissionsUseCase(
        session_factory=session_factory,
        user_role_repository_factory=lambda _s: user_role_repo,
        role_repository_factory=lambda _s: role_repo,
        role_permission_repository_factory=lambda _s: role_permission_repo,
    )


def _role(role_id: str, *, is_active: bool = True, tenant_id: str = TENANT_ID) -> Role:
    return Role(
        id=role_id,
        tenant_id=tenant_id,
        name=f"Role {role_id}",
        description=None,
        default_scope=RoleScope.BRANCH,
        is_system=True,
        is_active=is_active,
        created_at=NOW,
    )


def _grant(
    grant_id: str, role_id: str, *, branch_id: str | None, tenant_id: str = TENANT_ID
) -> UserRole:
    return UserRole(
        id=grant_id,
        tenant_id=tenant_id,
        user_id=USER_ID,
        role_id=role_id,
        branch_id=branch_id,
        granted_at=NOW,
        granted_by_user_id=None,
    )


async def test_a_user_with_no_grants_resolves_to_empty(session_factory) -> None:
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository(),
        InMemoryRolePermissionRepository(),
        InMemoryUserRoleRepository(),
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.tenant_wide == frozenset()
    assert resolved.by_branch == {}
    assert resolved.all_codes == frozenset()


async def test_a_tenant_wide_grant_resolves_to_tenant_wide_codes(session_factory) -> None:
    role = _role("role-owner")
    role_permission_repo = InMemoryRolePermissionRepository()
    await role_permission_repo.replace_for_role(role.id, frozenset({"roles.assign", "menu.manage"}))
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository({role.id: role}),
        role_permission_repo,
        InMemoryUserRoleRepository({"g1": _grant("g1", role.id, branch_id=None)}),
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.tenant_wide == frozenset({"roles.assign", "menu.manage"})
    assert resolved.has("roles.assign")
    assert resolved.has("menu.manage", branch_id=BRANCH_A), "tenant-wide covers every branch"


async def test_a_branch_scoped_grant_resolves_only_to_that_branch(session_factory) -> None:
    role = _role("role-waiter")
    role_permission_repo = InMemoryRolePermissionRepository()
    await role_permission_repo.replace_for_role(role.id, frozenset({"table.read"}))
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository({role.id: role}),
        role_permission_repo,
        InMemoryUserRoleRepository({"g1": _grant("g1", role.id, branch_id=BRANCH_A)}),
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.tenant_wide == frozenset()
    assert resolved.has("table.read", branch_id=BRANCH_A) is True
    assert resolved.has("table.read", branch_id=BRANCH_B) is False
    assert resolved.has("table.read") is False, "no branch_id given means tenant-wide-only check"


async def test_multiple_simultaneous_roles_at_different_scopes_all_aggregate(
    session_factory,
) -> None:
    """The RBAC doc's own worked example: one user holding a tenant-wide
    role plus a distinct branch-scoped role at the same time."""
    tenant_role = _role("role-owner")
    branch_role = _role("role-manager")
    role_permission_repo = InMemoryRolePermissionRepository()
    await role_permission_repo.replace_for_role(tenant_role.id, frozenset({"roles.assign"}))
    await role_permission_repo.replace_for_role(branch_role.id, frozenset({"branch.manage"}))
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository({tenant_role.id: tenant_role, branch_role.id: branch_role}),
        role_permission_repo,
        InMemoryUserRoleRepository(
            {
                "g1": _grant("g1", tenant_role.id, branch_id=None),
                "g2": _grant("g2", branch_role.id, branch_id=BRANCH_A),
            }
        ),
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.tenant_wide == frozenset({"roles.assign"})
    assert resolved.by_branch == {BRANCH_A: frozenset({"branch.manage"})}
    assert resolved.all_codes == frozenset({"roles.assign", "branch.manage"})


async def test_two_branch_grants_for_the_same_user_both_aggregate_independently(
    session_factory,
) -> None:
    role = _role("role-manager")
    role_permission_repo = InMemoryRolePermissionRepository()
    await role_permission_repo.replace_for_role(role.id, frozenset({"branch.manage"}))
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository({role.id: role}),
        role_permission_repo,
        InMemoryUserRoleRepository(
            {
                "g1": _grant("g1", role.id, branch_id=BRANCH_A),
                "g2": _grant("g2", role.id, branch_id=BRANCH_B),
            }
        ),
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.by_branch == {
        BRANCH_A: frozenset({"branch.manage"}),
        BRANCH_B: frozenset({"branch.manage"}),
    }


async def test_a_grant_referencing_an_inactive_role_contributes_nothing(session_factory) -> None:
    role = _role("role-retired", is_active=False)
    role_permission_repo = InMemoryRolePermissionRepository()
    await role_permission_repo.replace_for_role(role.id, frozenset({"menu.manage"}))
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository({role.id: role}),
        role_permission_repo,
        InMemoryUserRoleRepository({"g1": _grant("g1", role.id, branch_id=None)}),
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.all_codes == frozenset()


async def test_a_grant_referencing_a_missing_role_contributes_nothing_and_does_not_raise(
    session_factory,
) -> None:
    """Defense-in-depth: even though ON DELETE RESTRICT should make this
    impossible in the real schema, resolution must never crash on one
    bad grant -- it should simply skip it and keep resolving the rest."""
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository(),  # no roles at all
        InMemoryRolePermissionRepository(),
        InMemoryUserRoleRepository({"g1": _grant("g1", "role-does-not-exist", branch_id=None)}),
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.all_codes == frozenset()


async def test_a_retired_permission_drops_out_even_with_a_stale_role_permission_row(
    session_factory,
) -> None:
    role = _role("role-owner")
    role_permission_repo = InMemoryRolePermissionRepository()
    await role_permission_repo.replace_for_role(role.id, frozenset({"roles.assign", "menu.manage"}))
    role_permission_repo.set_active_permission_codes(frozenset({"roles.assign"}))
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository({role.id: role}),
        role_permission_repo,
        InMemoryUserRoleRepository({"g1": _grant("g1", role.id, branch_id=None)}),
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.tenant_wide == frozenset({"roles.assign"})


async def test_a_revoked_grant_is_excluded_from_resolution(session_factory) -> None:
    role = _role("role-owner")
    role_permission_repo = InMemoryRolePermissionRepository()
    await role_permission_repo.replace_for_role(role.id, frozenset({"roles.assign"}))
    user_role_repo = InMemoryUserRoleRepository({"g1": _grant("g1", role.id, branch_id=None)})
    await user_role_repo.revoke(TENANT_ID, "g1")
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository({role.id: role}),
        role_permission_repo,
        user_role_repo,
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.all_codes == frozenset()


async def test_tenant_isolation_a_grant_in_another_tenant_is_never_resolved(
    session_factory,
) -> None:
    role = _role("role-owner", tenant_id=OTHER_TENANT_ID)
    role_permission_repo = InMemoryRolePermissionRepository()
    await role_permission_repo.replace_for_role(role.id, frozenset({"roles.assign"}))
    use_case = _make_use_case(
        session_factory,
        InMemoryRoleRepository({role.id: role}),
        role_permission_repo,
        InMemoryUserRoleRepository(
            {"g1": _grant("g1", role.id, branch_id=None, tenant_id=OTHER_TENANT_ID)}
        ),
    )

    resolved = await use_case.execute(TENANT_ID, USER_ID)

    assert resolved.all_codes == frozenset()
