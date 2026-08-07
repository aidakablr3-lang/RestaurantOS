"""Integration tests for the identity module's SQLAlchemy repositories.

Requires TEST_DATABASE_URL (see tests/integration/conftest.py). Runs the
real Alembic migration, including Row-Level Security policies — the
cross-tenant isolation test below is the single most important test in
this PR, verifying the RLS *policy itself*, independent of and in
addition to the repository's own application-layer tenant filter (Data
Architecture v2.0 SS4.1's "both layers must independently agree").
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.domain.entities import (
    Session,
    Tenant,
    TenantStatus,
    TenantTier,
    User,
    UserStatus,
)
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemySessionRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


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
        # Tenants are platform-root rows, not RLS-protected, so no prior
        # tenant context is required to insert one directly via raw SQL.
        await uow.session.execute(
            text(
                "INSERT INTO tenants (id, legal_name, display_name, tenant_tier, status, "
                "default_currency_code) VALUES (:id, :legal_name, :display_name, "
                ":tenant_tier, :status, :currency)"
            ),
            {
                "id": tenant.id,
                "legal_name": tenant.legal_name,
                "display_name": tenant.display_name,
                "tenant_tier": tenant.tenant_tier.value,
                "status": tenant.status.value,
                "currency": tenant.default_currency_code,
            },
        )
    return tenant


async def _create_user(session_factory, tenant_id: str, email: str, **overrides) -> User:
    user_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash, permission_version, "
                "status) VALUES (:id, :tenant_id, :email, :password_hash, 1, :status)"
            ),
            {
                "id": user_id,
                "tenant_id": tenant_id,
                "email": email,
                "password_hash": overrides.get("password_hash", "hashed::secret"),
                "status": overrides.get("status", UserStatus.ACTIVE).value,
            },
        )
    return await _fetch_user(session_factory, tenant_id, user_id)


async def _fetch_user(session_factory, tenant_id: str, user_id: str) -> User:
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        repo = SQLAlchemyUserRepository(uow.session)
        user = await repo.get_by_id(tenant_id, user_id)
        assert user is not None
        return user


class TestTenantRepository:
    async def test_get_by_id_returns_none_for_unknown_tenant(self, session_factory) -> None:
        async with UnitOfWork(session_factory) as uow:
            repo = SQLAlchemyTenantRepository(uow.session)
            assert await repo.get_by_id(generate_ulid()) is None

    async def test_get_by_id_returns_the_tenant(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        async with UnitOfWork(session_factory) as uow:
            repo = SQLAlchemyTenantRepository(uow.session)
            found = await repo.get_by_id(tenant.id)
        assert found is not None
        assert found.id == tenant.id
        assert found.status == TenantStatus.ACTIVE


class TestUserRepository:
    async def test_get_by_email_is_scoped_to_tenant(self, session_factory) -> None:
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        user_a = await _create_user(session_factory, tenant_a.id, "owner@example.com")
        await _create_user(session_factory, tenant_b.id, "owner@example.com")

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            repo = SQLAlchemyUserRepository(uow.session)
            found = await repo.get_by_email(tenant_a.id, "owner@example.com")

        assert found is not None
        assert found.id == user_a.id
        assert found.tenant_id == tenant_a.id

    async def test_row_level_security_blocks_cross_tenant_reads_even_without_an_app_filter(
        self, session_factory
    ) -> None:
        """The single most important test in this PR.

        Data Architecture v2.0 SS4.7: cross-tenant protection must be
        *verified*, not merely designed. This issues a raw,
        deliberately UNFILTERED query (no WHERE tenant_id clause at
        all — bypassing the repository's own application-layer
        scoping entirely) to prove the database's Row-Level Security
        policy is what actually stops Tenant B's row from coming back,
        independent of any application code.
        """
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        await _create_user(session_factory, tenant_a.id, "a@example.com")
        await _create_user(session_factory, tenant_b.id, "b@example.com")

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            # Deliberately no tenant_id predicate here.
            result = await uow.session.execute(text("SELECT tenant_id, email FROM users"))
            rows = result.all()

        assert len(rows) == 1, "RLS must hide every row outside the current tenant context"
        assert rows[0].tenant_id == tenant_a.id
        assert rows[0].email == "a@example.com"

    async def test_get_by_id_excludes_soft_deleted_users(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        user = await _create_user(session_factory, tenant.id, "gone@example.com")

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            await uow.session.execute(
                text("UPDATE users SET deleted_at = now() WHERE id = :id"), {"id": user.id}
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyUserRepository(uow.session)
            assert await repo.get_by_id(tenant.id, user.id) is None

    async def test_bump_permission_version_increments_and_is_returned(
        self, session_factory
    ) -> None:
        tenant = await _create_tenant(session_factory)
        user = await _create_user(session_factory, tenant.id, "owner@example.com")

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyUserRepository(uow.session)
            new_version = await repo.bump_permission_version(tenant.id, user.id)

        assert new_version == user.permission_version + 1

    async def test_partial_unique_index_allows_email_reuse_after_soft_delete(
        self, session_factory
    ) -> None:
        tenant = await _create_tenant(session_factory)
        first_user = await _create_user(session_factory, tenant.id, "reused@example.com")

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            await uow.session.execute(
                text("UPDATE users SET deleted_at = now() WHERE id = :id"),
                {"id": first_user.id},
            )

        # Must not raise a unique-constraint violation.
        second_user = await _create_user(session_factory, tenant.id, "reused@example.com")
        assert second_user.id != first_user.id


class TestSessionRepository:
    async def test_create_and_get_by_refresh_token_hash(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        user = await _create_user(session_factory, tenant.id, "owner@example.com")
        now = datetime.now(UTC)
        session = Session(
            id=generate_ulid(),
            tenant_id=tenant.id,
            user_id=user.id,
            device_id=None,
            refresh_token_hash="hashed::abc123",
            issued_at=now,
            expires_at=now + timedelta(days=30),
            revoked_at=None,
        )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemySessionRepository(uow.session)
            await repo.create(session)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemySessionRepository(uow.session)
            found = await repo.get_by_refresh_token_hash(tenant.id, "hashed::abc123")

        assert found is not None
        assert found.id == session.id

    async def test_revoke_sets_revoked_at(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        user = await _create_user(session_factory, tenant.id, "owner@example.com")
        now = datetime.now(UTC)
        session = Session(
            id=generate_ulid(),
            tenant_id=tenant.id,
            user_id=user.id,
            device_id=None,
            refresh_token_hash="hashed::xyz",
            issued_at=now,
            expires_at=now + timedelta(days=30),
            revoked_at=None,
        )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemySessionRepository(uow.session)
            await repo.create(session)
            await repo.revoke(session.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemySessionRepository(uow.session)
            found = await repo.get_by_refresh_token_hash(tenant.id, "hashed::xyz")

        assert found is not None
        assert found.revoked_at is not None

    async def test_revoke_all_for_user_revokes_only_that_users_sessions(
        self, session_factory
    ) -> None:
        tenant = await _create_tenant(session_factory)
        user_a = await _create_user(session_factory, tenant.id, "a@example.com")
        user_b = await _create_user(session_factory, tenant.id, "b@example.com")
        now = datetime.now(UTC)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemySessionRepository(uow.session)
            await repo.create(
                Session(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    user_id=user_a.id,
                    device_id=None,
                    refresh_token_hash="hashed::a1",
                    issued_at=now,
                    expires_at=now + timedelta(days=30),
                    revoked_at=None,
                )
            )
            await repo.create(
                Session(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    user_id=user_b.id,
                    device_id=None,
                    refresh_token_hash="hashed::b1",
                    issued_at=now,
                    expires_at=now + timedelta(days=30),
                    revoked_at=None,
                )
            )
            await repo.revoke_all_for_user(user_a.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemySessionRepository(uow.session)
            session_a = await repo.get_by_refresh_token_hash(tenant.id, "hashed::a1")
            session_b = await repo.get_by_refresh_token_hash(tenant.id, "hashed::b1")

        assert session_a is not None and session_a.revoked_at is not None
        assert session_b is not None and session_b.revoked_at is None
