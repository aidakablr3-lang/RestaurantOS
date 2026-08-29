"""Integration tests for the RBAC repositories, real Row-Level Security,
and real database constraints (RBAC Foundation Architecture SS13/SS14).

Requires TEST_DATABASE_URL (see tests/integration/conftest.py). Follows
test_repositories.py's own pattern exactly: the cross-tenant RLS test
issues a deliberately unfiltered raw query to prove the *database
policy* blocks the row, independent of any repository-level filter.

The `roles` table's RLS policy is a deliberate deviation from every
other tenant-scoped table's plain `tenant_id = current_setting(...)`
predicate: `tenant_id IS NULL OR tenant_id = current_setting(...)`,
because a plain predicate would hide platform-wide (NULL) rows
entirely. That widened predicate is exactly what
test_roles_rls_shows_platform_wide_roles_from_any_tenant_context below
proves -- not merely designed, verified.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.domain.entities import (
    Role,
    RolePermission,
    RoleScope,
    Tenant,
    TenantStatus,
    TenantTier,
    UserRole,
)
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyPermissionRepository,
    SQLAlchemyRolePermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRoleRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

# Seeded once by the 0003 migration itself -- fixed platform reference
# data, safe to depend on directly (see tests/integration/conftest.py's
# note on why `permissions` is never truncated between tests).
SEEDED_PERMISSION_CODE = "menu.read"
SEEDED_PERMISSION_CODE_2 = "menu.manage"


async def _create_tenant(session_factory, **overrides) -> Tenant:
    tenant = Tenant(
        id=generate_ulid(),
        legal_name=overrides.get("legal_name", "Acme Restaurants Inc."),
        display_name=overrides.get("display_name", "Acme"),
        tenant_tier=TenantTier.SHARED,
        status=overrides.get("status", TenantStatus.ACTIVE),
        default_currency_code="USD",
        created_at=datetime.now(UTC),
    )
    async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
        repo = SQLAlchemyTenantRepository(uow.session)
        await repo.create(tenant)
    return tenant


async def _create_role(
    session_factory, tenant_id: str | None, *, name: str = "Branch Manager"
) -> Role:
    role = Role(
        id=generate_ulid(),
        tenant_id=tenant_id,
        name=name,
        description="test role",
        default_scope=RoleScope.BRANCH,
        is_system=False,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    # A platform-wide role (tenant_id=None) has no tenant context to
    # scope the insert to -- use whichever tenant_id is available, same
    # as _create_tenant's own "platform-root row" precedent.
    context = TenantContext(tenant_id) if tenant_id is not None else None
    async with UnitOfWork(session_factory, context) as uow:
        repo = SQLAlchemyRoleRepository(uow.session)
        return await repo.create(role)


async def _create_user_role(
    session_factory,
    tenant_id: str,
    user_id: str,
    role_id: str,
    *,
    branch_id: str | None = None,
) -> UserRole:
    user_role = UserRole(
        id=generate_ulid(),
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role_id,
        branch_id=branch_id,
        granted_at=datetime.now(UTC),
        granted_by_user_id=None,
    )
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        repo = SQLAlchemyUserRoleRepository(uow.session)
        return await repo.create(user_role)


async def _create_branch(session_factory, tenant_id: str) -> str:
    """A real ``branches`` row (Restaurant Platform migration 0004) --
    required since 0004 closed the cross-migration dependency 0003's
    own docstring disclosed: ``user_roles.branch_id`` now has a real FK
    plus a trigger enforcing it belongs to the same tenant as the grant
    itself. Direct raw SQL, not the restaurant module's own repository,
    matching this file's existing "insert directly for FK-satisfying
    fixture data" convention (``_create_tenant``, ``_create_role``)
    rather than introducing a cross-module test dependency."""
    restaurant_id = generate_ulid()
    branch_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO restaurants (id, tenant_id, legal_name, display_name, "
                "default_currency_code) VALUES (:id, :tenant_id, 'Test Restaurant', "
                "'Test Restaurant', 'USD')"
            ),
            {"id": restaurant_id, "tenant_id": tenant_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO branches (id, tenant_id, restaurant_id, name, invoice_prefix) "
                "VALUES (:id, :tenant_id, :restaurant_id, 'Test Branch', 'TST')"
            ),
            {"id": branch_id, "tenant_id": tenant_id, "restaurant_id": restaurant_id},
        )
    return branch_id


async def _create_user(session_factory, tenant_id: str, email: str) -> str:
    user_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash, permission_version, "
                "status) VALUES (:id, :tenant_id, :email, 'hashed::x', 1, 'active')"
            ),
            {"id": user_id, "tenant_id": tenant_id, "email": email},
        )
    return user_id


class TestPermissionRepository:
    async def test_list_active_includes_the_0003_migration_seed_data(self, session_factory) -> None:
        async with UnitOfWork(session_factory) as uow:
            repo = SQLAlchemyPermissionRepository(uow.session)
            permissions = await repo.list_active()

        codes = {p.code for p in permissions}
        assert SEEDED_PERMISSION_CODE in codes
        assert "roles.assign" in codes
        # 11 from 0003 + 12 from 0007 (Sprint 7 Step 2, Operations module)
        # + 1 from 0010 (reports.read, the End-of-Day report gap fix)
        # + 2 from 0012 (inventory_food.manage/read, the food-vs-beverage
        # inventory permission split).
        assert len(permissions) == 26

    async def test_get_by_code_returns_none_for_unknown_code(self, session_factory) -> None:
        async with UnitOfWork(session_factory) as uow:
            repo = SQLAlchemyPermissionRepository(uow.session)
            assert await repo.get_by_code("no.such.permission") is None

    async def test_get_by_code_returns_a_seeded_permission(self, session_factory) -> None:
        async with UnitOfWork(session_factory) as uow:
            repo = SQLAlchemyPermissionRepository(uow.session)
            found = await repo.get_by_code(SEEDED_PERMISSION_CODE)

        assert found is not None
        assert found.code == SEEDED_PERMISSION_CODE
        assert found.is_active is True


class TestRoleRepository:
    async def test_create_and_get_by_id(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRoleRepository(uow.session)
            found = await repo.get_by_id(tenant.id, role.id)

        assert found is not None
        assert found.name == "Branch Manager"
        assert found.tenant_id == tenant.id

    async def test_get_by_name_is_scoped_to_tenant(self, session_factory) -> None:
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        await _create_role(session_factory, tenant_a.id, name="Owner")
        await _create_role(session_factory, tenant_b.id, name="Owner")

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            repo = SQLAlchemyRoleRepository(uow.session)
            found = await repo.get_by_name(tenant_a.id, "Owner")

        assert found is not None
        assert found.tenant_id == tenant_a.id

    async def test_a_platform_wide_role_is_visible_from_any_tenant_context(
        self, session_factory
    ) -> None:
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        platform_role = await _create_role(session_factory, None, name="Platform Wide Role")

        async with UnitOfWork(session_factory, TenantContext(tenant_b.id)) as uow:
            repo = SQLAlchemyRoleRepository(uow.session)
            found = await repo.get_by_id(tenant_b.id, platform_role.id)

        assert found is not None
        assert found.tenant_id is None
        assert tenant_a.id != tenant_b.id  # sanity: genuinely two different tenants

    async def test_list_for_tenant_includes_own_and_platform_wide_but_not_other_tenants(
        self, session_factory
    ) -> None:
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        own_role = await _create_role(session_factory, tenant_a.id, name="Own Role")
        platform_role = await _create_role(session_factory, None, name="Platform Role")
        await _create_role(session_factory, tenant_b.id, name="Someone Elses Role")

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            repo = SQLAlchemyRoleRepository(uow.session)
            roles, total = await repo.list_for_tenant(tenant_a.id, offset=0, limit=100)

        names = {r.name for r in roles}
        assert own_role.name in names
        assert platform_role.name in names
        assert "Someone Elses Role" not in names
        assert total == 2

    async def test_update_persists_a_deactivated_role(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)
        role.deactivate()

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRoleRepository(uow.session)
            await repo.update(role)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRoleRepository(uow.session)
            found = await repo.get_by_id(tenant.id, role.id)
        assert found is not None
        assert found.is_active is False

    async def test_duplicate_role_name_in_the_same_tenant_raises_integrity_error(
        self, session_factory
    ) -> None:
        """The application-layer name-conflict check (CreateRoleUseCase)
        is belt; this is the suspenders -- UNIQUE NULLS NOT DISTINCT
        (tenant_id, name) is the real guarantee under a race."""
        tenant = await _create_tenant(session_factory)
        await _create_role(session_factory, tenant.id, name="Owner")

        with pytest.raises(IntegrityError):
            await _create_role(session_factory, tenant.id, name="Owner")

    async def test_row_level_security_blocks_cross_tenant_role_reads(self, session_factory) -> None:
        """The RBAC analogue of test_repositories.py's own
        'single most important test' -- a deliberately unfiltered raw
        query, proving the database policy (not application code) is
        what hides another tenant's role."""
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        await _create_role(session_factory, tenant_a.id, name="Tenant A Only Role")
        await _create_role(session_factory, tenant_b.id, name="Tenant B Only Role")

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            result = await uow.session.execute(
                text("SELECT tenant_id, name FROM roles WHERE tenant_id IS NOT NULL")
            )
            rows = result.all()

        assert len(rows) == 1, "RLS must hide every tenant-scoped role outside the current tenant"
        assert rows[0].tenant_id == tenant_a.id
        assert rows[0].name == "Tenant A Only Role"

    async def test_roles_rls_shows_platform_wide_roles_from_any_tenant_context(
        self, session_factory
    ) -> None:
        """Proves the *widened* predicate specifically
        (`tenant_id IS NULL OR tenant_id = current_setting(...)`) --
        the deliberate deviation from the plain predicate every other
        tenant-scoped table uses."""
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        await _create_role(session_factory, None, name="Truly Platform Wide")
        await _create_role(session_factory, tenant_b.id, name="Tenant B Private Role")

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            result = await uow.session.execute(text("SELECT tenant_id, name FROM roles"))
            rows = {row.name: row.tenant_id for row in result.all()}

        assert "Truly Platform Wide" in rows
        assert rows["Truly Platform Wide"] is None
        assert "Tenant B Private Role" not in rows


class TestRolePermissionRepository:
    async def test_replace_for_role_is_atomic_and_fully_replaces(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            await repo.replace_for_role(
                role.id, frozenset({SEEDED_PERMISSION_CODE, SEEDED_PERMISSION_CODE_2})
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            codes = await repo.list_permission_codes_for_role(role.id)
        assert codes == frozenset({SEEDED_PERMISSION_CODE, SEEDED_PERMISSION_CODE_2})

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            await repo.replace_for_role(role.id, frozenset({SEEDED_PERMISSION_CODE}))

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            codes = await repo.list_permission_codes_for_role(role.id)
        assert codes == frozenset({SEEDED_PERMISSION_CODE})

    async def test_list_permission_codes_excludes_inactive_permissions(
        self, session_factory
    ) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            await repo.replace_for_role(role.id, frozenset({SEEDED_PERMISSION_CODE}))
            # Simulate the permission being retired *after* the grant --
            # a stale RolePermission row must drop out of resolution.
            await uow.session.execute(
                text("UPDATE permissions SET is_active = false WHERE code = :code"),
                {"code": SEEDED_PERMISSION_CODE},
            )

        try:
            async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
                repo = SQLAlchemyRolePermissionRepository(uow.session)
                codes = await repo.list_permission_codes_for_role(role.id)
            assert codes == frozenset()
        finally:
            async with UnitOfWork(session_factory) as uow:
                await uow.session.execute(
                    text("UPDATE permissions SET is_active = true WHERE code = :code"),
                    {"code": SEEDED_PERMISSION_CODE},
                )

    async def test_add_and_remove_a_single_permission(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            await repo.add(
                RolePermission(
                    id=generate_ulid(),
                    role_id=role.id,
                    permission_code=SEEDED_PERMISSION_CODE,
                    created_at=datetime.now(UTC),
                )
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            assert await repo.list_permission_codes_for_role(role.id) == frozenset(
                {SEEDED_PERMISSION_CODE}
            )
            await repo.remove(role.id, SEEDED_PERMISSION_CODE)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            assert await repo.list_permission_codes_for_role(role.id) == frozenset()

    async def test_deleting_a_role_cascades_to_its_role_permissions(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            await repo.replace_for_role(role.id, frozenset({SEEDED_PERMISSION_CODE}))

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            await uow.session.execute(text("DELETE FROM roles WHERE id = :id"), {"id": role.id})

        async with UnitOfWork(session_factory) as uow:
            remaining = await uow.session.execute(
                text("SELECT count(*) FROM role_permissions WHERE role_id = :id"), {"id": role.id}
            )
            assert remaining.scalar() == 0

    async def test_removing_a_permission_that_still_backs_a_role_permission_is_restricted(
        self, session_factory
    ) -> None:
        """ON DELETE RESTRICT on role_permissions.permission_code: a
        Permission still referenced by a RolePermission cannot be
        hard-deleted (only deactivated -- see the excludes-inactive test
        above for the correct way to retire one)."""
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRolePermissionRepository(uow.session)
            await repo.replace_for_role(role.id, frozenset({SEEDED_PERMISSION_CODE}))

        with pytest.raises(IntegrityError):
            async with UnitOfWork(session_factory) as uow:
                await uow.session.execute(
                    text("DELETE FROM permissions WHERE code = :code"),
                    {"code": SEEDED_PERMISSION_CODE},
                )


class TestUserRoleRepository:
    async def test_create_and_get_by_id(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)
        user_id = await _create_user(session_factory, tenant.id, "user@example.com")
        user_role = await _create_user_role(session_factory, tenant.id, user_id, role.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyUserRoleRepository(uow.session)
            found = await repo.get_by_id(tenant.id, user_role.id)

        assert found is not None
        assert found.user_id == user_id
        assert found.branch_id is None

    async def test_list_active_for_user_returns_both_tenant_wide_and_branch_scoped_grants(
        self, session_factory
    ) -> None:
        tenant = await _create_tenant(session_factory)
        tenant_role = await _create_role(session_factory, tenant.id, name="Owner")
        branch_role = await _create_role(session_factory, tenant.id, name="Manager")
        user_id = await _create_user(session_factory, tenant.id, "user@example.com")
        branch_id = await _create_branch(session_factory, tenant.id)
        await _create_user_role(session_factory, tenant.id, user_id, tenant_role.id, branch_id=None)
        await _create_user_role(
            session_factory, tenant.id, user_id, branch_role.id, branch_id=branch_id
        )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyUserRoleRepository(uow.session)
            grants = await repo.list_active_for_user(tenant.id, user_id)

        assert len(grants) == 2
        branch_ids = {g.branch_id for g in grants}
        assert branch_ids == {None, branch_id}

    async def test_exists_mirrors_the_database_unique_constraint(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)
        user_id = await _create_user(session_factory, tenant.id, "user@example.com")
        branch_id = await _create_branch(session_factory, tenant.id)
        other_branch_id = await _create_branch(session_factory, tenant.id)
        await _create_user_role(session_factory, tenant.id, user_id, role.id, branch_id=branch_id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyUserRoleRepository(uow.session)
            assert await repo.exists(tenant.id, user_id, role.id, branch_id) is True
            assert await repo.exists(tenant.id, user_id, role.id, other_branch_id) is False
            assert await repo.exists(tenant.id, user_id, role.id, None) is False

    async def test_duplicate_grant_at_the_same_scope_raises_integrity_error(
        self, session_factory
    ) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)
        user_id = await _create_user(session_factory, tenant.id, "user@example.com")
        await _create_user_role(session_factory, tenant.id, user_id, role.id, branch_id=None)

        with pytest.raises(IntegrityError):
            await _create_user_role(session_factory, tenant.id, user_id, role.id, branch_id=None)

    async def test_the_same_role_at_two_distinct_branches_is_not_a_duplicate(
        self, session_factory
    ) -> None:
        """UNIQUE NULLS NOT DISTINCT (user_id, role_id, branch_id): two
        non-NULL, distinct branch_id values are never considered
        duplicates of each other -- only genuinely equal tuples are."""
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)
        user_id = await _create_user(session_factory, tenant.id, "user@example.com")
        branch_a_id = await _create_branch(session_factory, tenant.id)
        branch_b_id = await _create_branch(session_factory, tenant.id)

        grant_a = await _create_user_role(
            session_factory, tenant.id, user_id, role.id, branch_id=branch_a_id
        )
        grant_b = await _create_user_role(
            session_factory, tenant.id, user_id, role.id, branch_id=branch_b_id
        )
        assert grant_a.id != grant_b.id

    async def test_revoke_soft_deletes_and_is_excluded_from_subsequent_reads(
        self, session_factory
    ) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)
        user_id = await _create_user(session_factory, tenant.id, "user@example.com")
        user_role = await _create_user_role(session_factory, tenant.id, user_id, role.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyUserRoleRepository(uow.session)
            revoked = await repo.revoke(tenant.id, user_role.id)
        assert revoked is not None
        assert revoked.id == user_role.id

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyUserRoleRepository(uow.session)
            assert await repo.get_by_id(tenant.id, user_role.id) is None
            assert await repo.list_active_for_user(tenant.id, user_id) == []

        # Revocation must be a soft delete, not a hard delete -- the row
        # (with deleted_at set) must still exist for audit purposes
        # (Data Architecture v1.0 SS3.1). Queried with the tenant's own
        # context set: user_roles' RLS policy has no NULL fallback (see
        # the roles-table docstring note above), so a query with no
        # tenant context at all would see nothing here regardless of
        # what the row actually contains.
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            still_there = await uow.session.execute(
                text("SELECT deleted_at FROM user_roles WHERE id = :id"), {"id": user_role.id}
            )
            row = still_there.one()
            assert row.deleted_at is not None

    async def test_revoking_an_already_revoked_grant_returns_none(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        role = await _create_role(session_factory, tenant.id)
        user_id = await _create_user(session_factory, tenant.id, "user@example.com")
        user_role = await _create_user_role(session_factory, tenant.id, user_id, role.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyUserRoleRepository(uow.session)
            await repo.revoke(tenant.id, user_role.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyUserRoleRepository(uow.session)
            assert await repo.revoke(tenant.id, user_role.id) is None

    async def test_row_level_security_blocks_cross_tenant_user_role_reads(
        self, session_factory
    ) -> None:
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        role_a = await _create_role(session_factory, tenant_a.id, name="Role A")
        role_b = await _create_role(session_factory, tenant_b.id, name="Role B")
        user_a = await _create_user(session_factory, tenant_a.id, "a@example.com")
        user_b = await _create_user(session_factory, tenant_b.id, "b@example.com")
        await _create_user_role(session_factory, tenant_a.id, user_a, role_a.id)
        await _create_user_role(session_factory, tenant_b.id, user_b, role_b.id)

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            result = await uow.session.execute(text("SELECT tenant_id FROM user_roles"))
            rows = result.all()

        assert len(rows) == 1
        assert rows[0].tenant_id == tenant_a.id
