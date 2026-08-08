"""Integration tests for ListAccessibleBranchesUseCase and
resolve_and_authorize_branch against real PostgreSQL (Step 4 Decision
Lock, Decisions 2 and 3).

Requires TEST_DATABASE_URL (see tests/integration/conftest.py). Every
scenario the Decision Lock's own test list named is covered here:
tenant-wide access, one branch, multiple branches, wrong branch, no
permission, cross-tenant branch, revoked role, and inactive role
(there is no separate "expired" grant state in the schema -- RBAC
grants are only ever revoked, never time-bound, confirmed in the
Decision Lock itself).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import Role, RoleScope, UserRole
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyRolePermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyUserRoleRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.application.use_cases.list_accessible_branches import (
    ListAccessibleBranchesUseCase,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyBranchRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "branch.read"


async def _create_tenant(session_factory) -> str:
    tenant_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO tenants (id, legal_name, display_name, tenant_tier, status, "
                "default_currency_code) VALUES (:id, 'Acme', 'Acme', 'shared', 'active', 'USD')"
            ),
            {"id": tenant_id},
        )
    return tenant_id


async def _create_user(session_factory, tenant_id: str) -> str:
    user_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash, permission_version, "
                "status) VALUES (:id, :tenant_id, :email, 'hashed::x', 1, 'active')"
            ),
            {"id": user_id, "tenant_id": tenant_id, "email": f"{user_id}@example.com"},
        )
    return user_id


async def _create_branch(session_factory, tenant_id: str, *, name: str = "Branch") -> str:
    restaurant_id = generate_ulid()
    branch_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO restaurants (id, tenant_id, legal_name, display_name, "
                "default_currency_code) VALUES (:id, :tenant_id, 'R', 'R', 'USD')"
            ),
            {"id": restaurant_id, "tenant_id": tenant_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO branches (id, tenant_id, restaurant_id, name) "
                "VALUES (:id, :tenant_id, :restaurant_id, :name)"
            ),
            {"id": branch_id, "tenant_id": tenant_id, "restaurant_id": restaurant_id, "name": name},
        )
    return branch_id


async def _grant_role(
    session_factory,
    *,
    tenant_id: str,
    user_id: str,
    branch_id: str | None,
    permission_code: str = PERMISSION_CODE,
    is_active: bool = True,
) -> str:
    """Seeds a real role + permission + UserRole grant, returning the
    UserRole's id (so a test can revoke it afterward)."""
    now = datetime.now(UTC)
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        role_repo = SQLAlchemyRoleRepository(uow.session)
        role_permission_repo = SQLAlchemyRolePermissionRepository(uow.session)
        user_role_repo = SQLAlchemyUserRoleRepository(uow.session)

        role = await role_repo.create(
            Role(
                id=generate_ulid(),
                tenant_id=tenant_id,
                name=f"Role {generate_ulid()}",
                description=None,
                default_scope=RoleScope.BRANCH if branch_id else RoleScope.TENANT,
                is_system=False,
                is_active=is_active,
                created_at=now,
            )
        )
        await role_permission_repo.replace_for_role(role.id, frozenset({permission_code}))
        user_role = await user_role_repo.create(
            UserRole(
                id=generate_ulid(),
                tenant_id=tenant_id,
                user_id=user_id,
                role_id=role.id,
                branch_id=branch_id,
                granted_at=now,
                granted_by_user_id=None,
            )
        )
    return user_role.id


def _resolve_use_case(session_factory) -> ResolveUserPermissionsUseCase:
    return ResolveUserPermissionsUseCase(
        session_factory=session_factory,
        user_role_repository_factory=SQLAlchemyUserRoleRepository,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
    )


def _list_accessible_branches_use_case(session_factory) -> ListAccessibleBranchesUseCase:
    return ListAccessibleBranchesUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=_resolve_use_case(session_factory),
    )


class TestListAccessibleBranchesUseCase:
    async def test_a_tenant_wide_grant_sees_every_branch_across_every_restaurant(
        self, session_factory
    ) -> None:
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        branch_a = await _create_branch(session_factory, tenant_id, name="A")
        branch_b = await _create_branch(session_factory, tenant_id, name="B")
        await _grant_role(session_factory, tenant_id=tenant_id, user_id=user_id, branch_id=None)

        use_case = _list_accessible_branches_use_case(session_factory)
        branches, total = await use_case.execute(
            tenant_id, user_id, PERMISSION_CODE, offset=0, limit=50
        )

        assert total == 2
        assert {b.id for b in branches} == {branch_a, branch_b}

    async def test_a_single_branch_grant_sees_only_that_branch(self, session_factory) -> None:
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        branch_a = await _create_branch(session_factory, tenant_id, name="A")
        await _create_branch(session_factory, tenant_id, name="B")  # never granted
        await _grant_role(session_factory, tenant_id=tenant_id, user_id=user_id, branch_id=branch_a)

        use_case = _list_accessible_branches_use_case(session_factory)
        branches, total = await use_case.execute(
            tenant_id, user_id, PERMISSION_CODE, offset=0, limit=50
        )

        assert total == 1
        assert {b.id for b in branches} == {branch_a}

    async def test_multiple_branch_grants_return_the_union(self, session_factory) -> None:
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        branch_a = await _create_branch(session_factory, tenant_id, name="A")
        branch_b = await _create_branch(session_factory, tenant_id, name="B")
        branch_c = await _create_branch(session_factory, tenant_id, name="C")  # never granted
        await _grant_role(session_factory, tenant_id=tenant_id, user_id=user_id, branch_id=branch_a)
        await _grant_role(session_factory, tenant_id=tenant_id, user_id=user_id, branch_id=branch_b)

        use_case = _list_accessible_branches_use_case(session_factory)
        branches, total = await use_case.execute(
            tenant_id, user_id, PERMISSION_CODE, offset=0, limit=50
        )

        assert total == 2
        assert {b.id for b in branches} == {branch_a, branch_b}
        assert branch_c not in {b.id for b in branches}

    async def test_a_branch_the_caller_was_never_granted_never_appears(
        self, session_factory
    ) -> None:
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        branch_a = await _create_branch(session_factory, tenant_id, name="A")
        wrong_branch = await _create_branch(session_factory, tenant_id, name="Wrong")
        await _grant_role(session_factory, tenant_id=tenant_id, user_id=user_id, branch_id=branch_a)

        use_case = _list_accessible_branches_use_case(session_factory)
        branches, _total = await use_case.execute(
            tenant_id, user_id, PERMISSION_CODE, offset=0, limit=50
        )

        assert wrong_branch not in {b.id for b in branches}

    async def test_no_permission_at_all_returns_an_empty_result(self, session_factory) -> None:
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        await _create_branch(session_factory, tenant_id, name="A")

        use_case = _list_accessible_branches_use_case(session_factory)
        branches, total = await use_case.execute(
            tenant_id, user_id, PERMISSION_CODE, offset=0, limit=50
        )

        assert branches == []
        assert total == 0

    async def test_tenant_membership_alone_never_grants_access(self, session_factory) -> None:
        """A user with zero RBAC grants, in a tenant that has real
        branches, sees none of them -- Decision 2's rule 5 verbatim."""
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        for name in ("A", "B", "C"):
            await _create_branch(session_factory, tenant_id, name=name)

        use_case = _list_accessible_branches_use_case(session_factory)
        branches, total = await use_case.execute(
            tenant_id, user_id, PERMISSION_CODE, offset=0, limit=50
        )

        assert total == 0
        assert branches == []

    async def test_a_revoked_grant_no_longer_grants_access(self, session_factory) -> None:
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        branch_a = await _create_branch(session_factory, tenant_id, name="A")
        user_role_id = await _grant_role(
            session_factory, tenant_id=tenant_id, user_id=user_id, branch_id=branch_a
        )

        async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
            await SQLAlchemyUserRoleRepository(uow.session).revoke(tenant_id, user_role_id)

        use_case = _list_accessible_branches_use_case(session_factory)
        branches, total = await use_case.execute(
            tenant_id, user_id, PERMISSION_CODE, offset=0, limit=50
        )

        assert total == 0
        assert branches == []

    async def test_an_inactive_role_no_longer_grants_access(self, session_factory) -> None:
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        branch_a = await _create_branch(session_factory, tenant_id, name="A")
        await _grant_role(
            session_factory,
            tenant_id=tenant_id,
            user_id=user_id,
            branch_id=branch_a,
            is_active=False,
        )

        use_case = _list_accessible_branches_use_case(session_factory)
        branches, total = await use_case.execute(
            tenant_id, user_id, PERMISSION_CODE, offset=0, limit=50
        )

        assert total == 0
        assert branches == []


class TestResolveAndAuthorizeBranch:
    async def test_a_caller_authorized_at_the_branch_is_allowed_through(
        self, session_factory
    ) -> None:
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        branch_a = await _create_branch(session_factory, tenant_id, name="A")
        await _grant_role(session_factory, tenant_id=tenant_id, user_id=user_id, branch_id=branch_a)
        resolved = await _resolve_use_case(session_factory).execute(tenant_id, user_id)

        async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
            branch = await resolve_and_authorize_branch(
                branch_repository=SQLAlchemyBranchRepository(uow.session),
                tenant_id=tenant_id,
                branch_id=branch_a,
                resolved_permissions=resolved,
                permission_code=PERMISSION_CODE,
            )

        assert branch.id == branch_a

    async def test_a_caller_authorized_at_a_different_branch_is_denied(
        self, session_factory
    ) -> None:
        tenant_id = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_id)
        branch_a = await _create_branch(session_factory, tenant_id, name="A")
        branch_b = await _create_branch(session_factory, tenant_id, name="B")
        await _grant_role(session_factory, tenant_id=tenant_id, user_id=user_id, branch_id=branch_a)
        resolved = await _resolve_use_case(session_factory).execute(tenant_id, user_id)

        async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
            try:
                await resolve_and_authorize_branch(
                    branch_repository=SQLAlchemyBranchRepository(uow.session),
                    tenant_id=tenant_id,
                    branch_id=branch_b,
                    resolved_permissions=resolved,
                    permission_code=PERMISSION_CODE,
                )
                raised = False
            except PermissionDeniedError:
                raised = True
        assert raised, "a branch the caller was never granted must be denied, not allowed"

    async def test_a_cross_tenant_branch_id_is_not_found_not_leaked_as_a_permission_denial(
        self, session_factory
    ) -> None:
        """The tenant-scoped repository lookup, not the permission
        check, is what rejects a cross-tenant id -- proving this stays
        a 404 (BranchNotFoundError), never a 403 that would confirm the
        id belongs to *someone*."""
        tenant_a = await _create_tenant(session_factory)
        tenant_b = await _create_tenant(session_factory)
        user_id = await _create_user(session_factory, tenant_a)
        other_tenants_branch = await _create_branch(session_factory, tenant_b, name="Other")
        await _grant_role(session_factory, tenant_id=tenant_a, user_id=user_id, branch_id=None)
        resolved = await _resolve_use_case(session_factory).execute(tenant_a, user_id)

        async with UnitOfWork(session_factory, TenantContext(tenant_a)) as uow:
            try:
                await resolve_and_authorize_branch(
                    branch_repository=SQLAlchemyBranchRepository(uow.session),
                    tenant_id=tenant_a,
                    branch_id=other_tenants_branch,
                    resolved_permissions=resolved,
                    permission_code=PERMISSION_CODE,
                )
                raised_not_found = False
            except BranchNotFoundError:
                raised_not_found = True
        assert raised_not_found

    async def test_list_by_ids_never_returns_a_cross_tenant_branch(self, session_factory) -> None:
        """Direct repository-layer proof, independent of RBAC's own
        trigger-level prevention (migration 0004's user_roles.branch_id
        tenant-consistency trigger already makes granting a cross-tenant
        branch id impossible at creation time) -- this is the
        belt-and-suspenders layer beneath that."""
        tenant_a = await _create_tenant(session_factory)
        tenant_b = await _create_tenant(session_factory)
        other_tenants_branch = await _create_branch(session_factory, tenant_b, name="Other")

        async with UnitOfWork(session_factory, TenantContext(tenant_a)) as uow:
            repo = SQLAlchemyBranchRepository(uow.session)
            result = await repo.list_by_ids(tenant_a, frozenset({other_tenants_branch}))

        assert result == []
