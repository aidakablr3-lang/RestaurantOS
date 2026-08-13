"""Idempotent seed for a fixed platform-admin tenant + user, used by
apps/admin-web's Playwright E2E suite (and available for manual/CI use
against any environment's DATABASE_URL).

Safe to run repeatedly against the same database: skips creating the
tenant if one with this legal name already exists, and skips creating
the user if one with this email already exists in that tenant.

No user-creation use case/endpoint exists yet (Sprint 4.1 Decision C --
an interim `is_platform_admin` boolean, no RBAC/admin-invite flow), so
the user row is inserted directly here, the same pattern the identity
module's own integration tests use. The tenant goes through
`TenantProvisioningService` so every provisioning invariant (starter
subscription, directory entry, default feature flag, outbox event)
stays correct.

Usage:
    DATABASE_URL=postgresql+asyncpg://... python scripts/seed_e2e_fixtures.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from restaurant_os_api.core.config import get_settings
from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.services import TenantProvisioningService
from restaurant_os_api.modules.identity.infrastructure.database.models import UserModel
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyFeatureFlagRepository,
    SQLAlchemyRolePermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemySubscriptionRepository,
    SQLAlchemyTenantDirectoryRepository,
    SQLAlchemyTenantRepository,
)
from restaurant_os_api.modules.identity.infrastructure.security import Argon2PasswordHasher
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

E2E_LEGAL_NAME = "RestaurantOS E2E Fixtures LLC"
E2E_DISPLAY_NAME = "E2E Fixtures"
E2E_ADMIN_EMAIL = "e2e-admin@restaurantos.dev"
E2E_ADMIN_PASSWORD = "E2EAdmin!2026"


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with UnitOfWork(session_factory) as uow:
        tenant_repo = SQLAlchemyTenantRepository(uow.session)
        existing = await tenant_repo.get_by_legal_name(E2E_LEGAL_NAME)

    if existing is not None:
        tenant_id = existing.id
        print(f"E2E tenant already exists: {tenant_id}")
    else:
        provisioning_service = TenantProvisioningService(
            session_factory=session_factory,
            tenant_repository_factory=SQLAlchemyTenantRepository,
            subscription_repository_factory=SQLAlchemySubscriptionRepository,
            feature_flag_repository_factory=SQLAlchemyFeatureFlagRepository,
            directory_repository_factory=SQLAlchemyTenantDirectoryRepository,
            role_repository_factory=SQLAlchemyRoleRepository,
            role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        )
        tenant = await provisioning_service.provision(
            legal_name=E2E_LEGAL_NAME,
            display_name=E2E_DISPLAY_NAME,
            default_currency_code="USD",
        )
        tenant_id = tenant.id
        print(f"Created E2E tenant: {tenant_id}")

    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        user_exists = await uow.session.scalar(
            text(
                "SELECT 1 FROM users WHERE tenant_id = :tenant_id AND email = :email "
                "AND deleted_at IS NULL"
            ),
            {"tenant_id": tenant_id, "email": E2E_ADMIN_EMAIL},
        )
        if user_exists:
            print(f"E2E admin user already exists: {E2E_ADMIN_EMAIL}")
        else:
            uow.session.add(
                UserModel(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    email=E2E_ADMIN_EMAIL,
                    phone=None,
                    password_hash=Argon2PasswordHasher().hash(E2E_ADMIN_PASSWORD),
                    pin_hash=None,
                    permission_version=1,
                    status="active",
                    is_platform_admin=True,
                    created_at=datetime.now(UTC),
                )
            )
            await uow.session.flush()
            print(f"Created E2E admin user: {E2E_ADMIN_EMAIL}")

    await engine.dispose()

    print("\nE2E fixtures ready:")
    print(f"  E2E_TENANT_ID={tenant_id}")
    print(f"  E2E_ADMIN_EMAIL={E2E_ADMIN_EMAIL}")
    print(f"  E2E_ADMIN_PASSWORD={E2E_ADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
