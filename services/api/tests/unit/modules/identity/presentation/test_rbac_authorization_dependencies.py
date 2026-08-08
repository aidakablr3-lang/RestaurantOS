"""Unit tests for require_permission / require_branch_permission (RBAC
Foundation Architecture SS8.1) -- the two FastAPI dependency factories
that gate every RBAC-protected route. Calling the returned async
function directly, bypassing FastAPI's own DI wiring entirely, is
sufficient since Annotated[...] parameter markers do not change how a
plain Python coroutine is called.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.dto import AuthenticatedPrincipalDTO
from restaurant_os_api.modules.identity.application.use_cases import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import Role, RoleScope, UserRole
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.identity.presentation.dependencies import (
    require_branch_permission,
    require_permission,
)
from tests.unit.modules.identity.fakes import (
    FakeAsyncSession,
    InMemoryRolePermissionRepository,
    InMemoryRoleRepository,
    InMemoryUserRoleRepository,
    fake_session_factory_returning,
)

NOW = datetime.now(UTC)
TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
USER_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
BRANCH_A = "01ARZ3NDEKTSV4RRFFQ6BRNCHA"
BRANCH_B = "01ARZ3NDEKTSV4RRFFQ6BRNCHB"
ROLE_ID = "role-1"


@pytest.fixture
def session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _principal(
    *, user_id: str = USER_ID, is_platform_admin: bool = False
) -> AuthenticatedPrincipalDTO:
    return AuthenticatedPrincipalDTO(
        user_id=user_id,
        tenant_id=TENANT_ID,
        session_id="session-1",
        device_id=None,
        is_platform_admin=is_platform_admin,
    )


def _resolve_use_case(session_factory, *, tenant_wide_codes=frozenset(), branch_codes=None):
    role_repo = InMemoryRoleRepository(
        {
            ROLE_ID: Role(
                id=ROLE_ID,
                tenant_id=TENANT_ID,
                name="Test Role",
                description=None,
                default_scope=RoleScope.BRANCH,
                is_system=True,
                is_active=True,
                created_at=NOW,
            )
        }
    )
    role_permission_repo = InMemoryRolePermissionRepository()
    user_role_repo = InMemoryUserRoleRepository()

    grants: dict[str, UserRole] = {}
    if tenant_wide_codes:
        grants["tw"] = UserRole(
            id="tw",
            tenant_id=TENANT_ID,
            user_id=USER_ID,
            role_id=ROLE_ID,
            branch_id=None,
            granted_at=NOW,
            granted_by_user_id=None,
        )
    for branch_id in branch_codes or {}:
        role_id = f"role-{branch_id}"
        role_repo._roles[role_id] = Role(
            id=role_id,
            tenant_id=TENANT_ID,
            name=f"Role at {branch_id}",
            description=None,
            default_scope=RoleScope.BRANCH,
            is_system=True,
            is_active=True,
            created_at=NOW,
        )
        grants[f"branch-{branch_id}"] = UserRole(
            id=f"branch-{branch_id}",
            tenant_id=TENANT_ID,
            user_id=USER_ID,
            role_id=role_id,
            branch_id=branch_id,
            granted_at=NOW,
            granted_by_user_id=None,
        )
    user_role_repo._user_roles = grants

    async def _seed() -> None:
        if tenant_wide_codes:
            await role_permission_repo.replace_for_role(ROLE_ID, frozenset(tenant_wide_codes))
        for branch_id, codes in (branch_codes or {}).items():
            await role_permission_repo.replace_for_role(f"role-{branch_id}", frozenset(codes))

    return (
        ResolveUserPermissionsUseCase(
            session_factory=session_factory,
            user_role_repository_factory=lambda _s: user_role_repo,
            role_repository_factory=lambda _s: role_repo,
            role_permission_repository_factory=lambda _s: role_permission_repo,
        ),
        _seed,
    )


class TestRequirePermission:
    async def test_allows_a_caller_holding_the_permission_tenant_wide(
        self, session_factory
    ) -> None:
        resolve, seed = _resolve_use_case(session_factory, tenant_wide_codes={"roles.assign"})
        await seed()
        dependency = require_permission("roles.assign")

        result = await dependency(_principal(), resolve)

        assert result.user_id == USER_ID

    async def test_denies_a_caller_with_no_grants_at_all(self, session_factory) -> None:
        resolve, seed = _resolve_use_case(session_factory)
        await seed()
        dependency = require_permission("roles.assign")

        with pytest.raises(PermissionDeniedError) as exc_info:
            await dependency(_principal(), resolve)
        assert exc_info.value.permission_code == "roles.assign"

    async def test_a_branch_only_grant_does_not_satisfy_a_tenant_wide_requirement(
        self, session_factory
    ) -> None:
        resolve, seed = _resolve_use_case(
            session_factory, branch_codes={BRANCH_A: {"roles.assign"}}
        )
        await seed()
        dependency = require_permission("roles.assign")

        with pytest.raises(PermissionDeniedError):
            await dependency(_principal(), resolve)

    async def test_is_platform_admin_does_not_bypass_the_gate(self, session_factory) -> None:
        """Deliberate: RBAC and the pre-existing is_platform_admin gate
        are two separate mechanisms (RBAC_Foundation_Architecture.md
        SS10.2) -- a platform admin with zero RBAC grants is still
        denied by require_permission."""
        resolve, seed = _resolve_use_case(session_factory)
        await seed()
        dependency = require_permission("roles.assign")

        with pytest.raises(PermissionDeniedError):
            await dependency(_principal(is_platform_admin=True), resolve)


class TestRequireBranchPermission:
    async def test_allows_a_caller_holding_the_permission_at_that_exact_branch(
        self, session_factory
    ) -> None:
        resolve, seed = _resolve_use_case(session_factory, branch_codes={BRANCH_A: {"table.read"}})
        await seed()
        dependency = require_branch_permission("table.read")

        result = await dependency(BRANCH_A, _principal(), resolve)

        assert result.user_id == USER_ID

    async def test_denies_a_caller_holding_the_permission_at_a_different_branch(
        self, session_factory
    ) -> None:
        resolve, seed = _resolve_use_case(session_factory, branch_codes={BRANCH_A: {"table.read"}})
        await seed()
        dependency = require_branch_permission("table.read")

        with pytest.raises(PermissionDeniedError) as exc_info:
            await dependency(BRANCH_B, _principal(), resolve)
        assert exc_info.value.branch_id == BRANCH_B

    async def test_a_tenant_wide_grant_satisfies_any_branch(self, session_factory) -> None:
        resolve, seed = _resolve_use_case(session_factory, tenant_wide_codes={"table.read"})
        await seed()
        dependency = require_branch_permission("table.read")

        result = await dependency(BRANCH_A, _principal(), resolve)

        assert result.user_id == USER_ID
