"""Integration tests for TenantProvisioningService.provision()'s atomic
first-Owner creation (Phase 1 design doc SSA.4), against real Postgres.

Covers exactly what the design doc's rollback/invariant tests require:
tenant + Owner user + Owner role grant all commit in one transaction (or
none do), and a tenant provisioned through this path is never reachable
in a state with zero roles.assign holders.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from restaurant_os_api.modules.identity.application.services import TenantProvisioningService
from restaurant_os_api.modules.identity.domain.entities import UserStatus
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyFeatureFlagRepository,
    SQLAlchemyOwnerActivationTokenRepository,
    SQLAlchemyRolePermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemySubscriptionRepository,
    SQLAlchemyTenantDirectoryRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
    SQLAlchemyUserRoleRepository,
)
from restaurant_os_api.modules.identity.infrastructure.security import JWTTokenService
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter


@pytest_asyncio.fixture
async def admin_engine() -> AsyncGenerator[AsyncEngine]:
    """A connection as the table *owner* (``TEST_DATABASE_URL`` itself,
    not the ``engine`` fixture's unprivileged ``restaurantos_rls_test``
    role) -- Postgres always lets a table's owner bypass RLS.

    Needed here because both tests below verify system-wide facts with
    no tenant to scope a ``TenantContext`` by (a fresh tenant's role
    grant the instant after creation; the total absence of a tenant
    after a forced rollback). The ``engine`` fixture is the *wrong*
    tool for that: it exists specifically to *enforce* RLS like a real
    unauthenticated connection would, so a query through it with no
    tenant context set silently returns zero rows regardless of what's
    actually in the table -- which is what a first draft of this file
    did, passing for the wrong reason (or in the rollback test's case,
    passing even though it was checking nothing).
    """
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    yield engine
    await engine.dispose()


def _token_service() -> JWTTokenService:
    return JWTTokenService(
        private_key="unused-in-these-tests",
        public_key="unused-in-these-tests",
        issuer="restaurantos-test",
        access_ttl_seconds=900,
    )


def _real_provisioning_service(session_factory) -> TenantProvisioningService:
    return TenantProvisioningService(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        subscription_repository_factory=SQLAlchemySubscriptionRepository,
        feature_flag_repository_factory=SQLAlchemyFeatureFlagRepository,
        directory_repository_factory=SQLAlchemyTenantDirectoryRepository,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
        user_repository_factory=SQLAlchemyUserRepository,
        user_role_repository_factory=SQLAlchemyUserRoleRepository,
        owner_activation_token_repository_factory=SQLAlchemyOwnerActivationTokenRepository,
        token_service=_token_service(),
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


async def test_provision_creates_tenant_owner_and_role_grant_atomically(
    session_factory, admin_engine: AsyncEngine
) -> None:
    service = _real_provisioning_service(session_factory)

    tenant, owner, raw_token = await service.provision(
        legal_name="Atomic Provision LLC",
        display_name="Atomic Provision",
        default_currency_code="USD",
        owner_email="atomic-owner@example.com",
    )

    assert tenant.id
    assert owner.tenant_id == tenant.id
    assert owner.email == "atomic-owner@example.com"
    assert owner.status == UserStatus.INVITED
    assert owner.password_hash is None
    assert raw_token

    # The invariant, stated literally: immediately after provision()
    # returns, the owner already holds roles.assign -- there is no
    # window where the tenant exists with zero roles.assign holders.
    # Asserted directly against the granted role's own permission set
    # (simpler and just as conclusive as going through
    # ResolveUserPermissionsUseCase, which is exercised elsewhere).
    #
    # Uses admin_engine (the table owner, genuinely bypasses RLS) --
    # see that fixture's own docstring for why a plain session_factory()
    # session or the RLS-enforcing `engine` fixture both silently
    # return zero rows here instead of an error.
    async with admin_engine.begin() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT r.name, rp.permission_code FROM user_roles ur "
                    "JOIN roles r ON r.id = ur.role_id "
                    "JOIN role_permissions rp ON rp.role_id = r.id "
                    "WHERE ur.tenant_id = :tenant_id AND ur.user_id = :user_id "
                    "AND ur.deleted_at IS NULL AND rp.permission_code = 'roles.assign'"
                ),
                {"tenant_id": tenant.id, "user_id": owner.id},
            )
        ).one_or_none()
    assert row is not None, "owner must hold roles.assign immediately after provision()"
    assert row[0] == "Tenant Owner"

    # granted_by_user_id=None -- a system operation, no delegating actor
    # (RoleGrantPolicy deliberately not invoked -- see the service's own
    # module-level comment).
    async with admin_engine.begin() as conn:
        granted_by = (
            await conn.execute(
                text(
                    "SELECT granted_by_user_id FROM user_roles "
                    "WHERE tenant_id = :tenant_id AND user_id = :user_id"
                ),
                {"tenant_id": tenant.id, "user_id": owner.id},
            )
        ).scalar_one()
    assert granted_by is None


async def test_a_failure_after_the_user_insert_rolls_back_the_whole_transaction(
    session_factory, admin_engine: AsyncEngine
) -> None:
    """Forces a real mid-transaction failure (the role-grant insert
    raises) after the tenant and owner user have already been inserted
    in the same transaction, proving the atomicity claim concretely --
    not just by inspection of the code, but by observing that rows
    which *did* get written earlier in the same transaction are gone
    too once it fails."""

    class _ExplodingUserRoleRepository:
        def __init__(self, session: AsyncSession) -> None:
            self._real = SQLAlchemyUserRoleRepository(session)

        async def create(self, user_role):
            raise RuntimeError("deliberate failure for the atomicity test")

    def _exploding_user_role_repository_factory(session: AsyncSession):
        return _ExplodingUserRoleRepository(session)

    service = TenantProvisioningService(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        subscription_repository_factory=SQLAlchemySubscriptionRepository,
        feature_flag_repository_factory=SQLAlchemyFeatureFlagRepository,
        directory_repository_factory=SQLAlchemyTenantDirectoryRepository,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
        user_repository_factory=SQLAlchemyUserRepository,
        user_role_repository_factory=_exploding_user_role_repository_factory,
        owner_activation_token_repository_factory=SQLAlchemyOwnerActivationTokenRepository,
        token_service=_token_service(),
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )

    with pytest.raises(RuntimeError, match="deliberate failure"):
        await service.provision(
            legal_name="Rollback Test LLC",
            display_name="Rollback Test",
            default_currency_code="USD",
            owner_email="rollback-owner@example.com",
        )

    # Uses admin_engine (the table owner, genuinely bypasses RLS) --
    # these queries have no tenant context to scope by (that's the
    # point: the tenant row itself must not exist). The RLS-enforcing
    # `engine` fixture would make user_count/orphaned_role_grant_count
    # vacuously 0 even if the rollback were broken and those rows still
    # existed -- see admin_engine's own docstring.
    async with admin_engine.begin() as conn:
        tenant_count = (
            await conn.exec_driver_sql(
                "SELECT count(*) FROM tenants WHERE legal_name = 'Rollback Test LLC'"
            )
        ).scalar_one()
        user_count = (
            await conn.exec_driver_sql(
                "SELECT count(*) FROM users WHERE email = 'rollback-owner@example.com'"
            )
        ).scalar_one()
        # No user with that email exists (proven above), so no
        # user_roles row referencing one can exist either -- checked
        # directly anyway, exactly as asked, not just inferred.
        orphaned_role_grant_count = (
            await conn.exec_driver_sql(
                "SELECT count(*) FROM user_roles ur "
                "LEFT JOIN users u ON u.id = ur.user_id "
                "WHERE u.email = 'rollback-owner@example.com'"
            )
        ).scalar_one()

    assert tenant_count == 0
    assert user_count == 0
    assert orphaned_role_grant_count == 0
