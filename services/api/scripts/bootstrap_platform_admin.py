"""One-time platform-admin bootstrap for a brand-new production database.

**Why this exists.** `POST /api/v1/admin/tenants` (the only tenant-creation
endpoint) is gated on `require_platform_admin`, which checks a
`users.is_platform_admin` boolean that no API call can ever set --
confirmed via source (`admin_tenant_router.py`'s own docstring: "gated on
`require_platform_admin`... `is_platform_admin=True`, not just some of
them"). There is no self-service "become the first platform admin" path
by design. `scripts/seed_e2e_fixtures.py` creates a platform-admin user
too, but with a hardcoded, publicly-known-in-this-repo password -- fine
for CI/E2E, never safe to run against a real production database. This
script is the real thing: a real email and password you choose, entered
once, never committed or logged.

**Idempotent by construction, not just by convention.** Refuses to do
anything if a platform-admin user already exists anywhere in the
database -- this script only ever creates the *first* one. Re-running it
against an already-bootstrapped database reports who the existing
platform admin is and makes no change, the same "report and stop" shape
`create_user.py`/`seed_e2e_fixtures.py` already use for their own
already-exists cases.

**The platform-admin user needs a tenant to hang off of** (`users.tenant_id`
is a hard `NOT NULL` foreign key -- confirmed via
`platform/database/mixins.py`'s `TenantScopedMixin`), the same structural
reason `seed_e2e_fixtures.py` provisions a throwaway tenant for its own
platform-admin user. This script provisions (or reuses, if already
present -- safe to re-run before the platform admin itself exists yet)
one fixed "RestaurantOS Platform Ops" tenant the same way, through the
real `TenantProvisioningService` so every provisioning invariant (starter
subscription, directory entry, default feature flag, outbox event) stays
correct. Nobody ever logs into this tenant directly -- it exists only to
satisfy the foreign key.

**What this script deliberately does NOT do:**
  - It never hardcodes a password. Pass `--password` (shell history/process
    list exposure -- avoid for the real thing) or omit it to get a
    freshly generated one, printed exactly once.
  - It never runs automatically -- no scheduler, migration hook, or
    app-startup call to this script exists anywhere.
  - By default (no `--apply`) it only prints what it would do and changes
    nothing.
  - It never re-grants or updates an existing platform admin's password
    or status -- if one exists, this script's job is already done.

Usage (matches scripts/deploy/04_bootstrap_platform_admin.sh, which runs
this inside the `api` container as part of the documented deploy
sequence -- see docs/DEPLOYMENT.md):

    # Preview only -- no writes:
    DATABASE_URL=postgresql+asyncpg://... python scripts/bootstrap_platform_admin.py \\
        --email you@prashanthai.com

    # Actually create, auto-generated password printed once:
    DATABASE_URL=postgresql+asyncpg://... python scripts/bootstrap_platform_admin.py \\
        --email you@prashanthai.com --apply
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from restaurant_os_api.core.config import get_settings
from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.services import TenantProvisioningService
from restaurant_os_api.modules.identity.infrastructure.database.models import UserModel
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
from restaurant_os_api.modules.identity.infrastructure.security import (
    Argon2PasswordHasher,
    JWTTokenService,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

_PLATFORM_OPS_LEGAL_NAME = "RestaurantOS Platform Ops"
_PLATFORM_OPS_DISPLAY_NAME = "Platform Ops"
# Never logged into -- provision() requires an owner_email argument, but
# nothing in this script's flow issues that owner a password or session.
# .invalid is the RFC 2606 reserved TLD for exactly this "never a real,
# reachable address" case.
_PLATFORM_OPS_OWNER_EMAIL_PLACEHOLDER = "platform-ops-owner@internal.invalid"


def _generate_password() -> str:
    # 16 chars of URL-safe base64 -- ~96 bits of entropy, comfortably
    # above what Argon2id needs to make offline cracking infeasible, and
    # short enough to read aloud/type once during handover. Same choice
    # create_user.py already makes.
    return secrets.token_urlsafe(12)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--email", required=True, help="Login email for the new platform admin.")
    parser.add_argument(
        "--password",
        default=None,
        help="Set an explicit password instead of generating one. Avoid for the real "
        "bootstrap -- bare CLI args land in shell history and process listings.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write the change. Without this flag, only previews what would happen.",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # `users` carries an RLS policy scoped by `app.tenant_id`
    # (`USING (tenant_id = current_setting('app.tenant_id', true))`) --
    # querying it with no TenantContext set (as every other script in
    # this repo does for a single known tenant) would silently see ZERO
    # rows regardless of what actually exists, since
    # `tenant_id = NULL` is never true. `tenants` itself carries no RLS
    # policy (Data Architecture v2.0 SS5.2 -- see the onboarding
    # module's own models.py docstring for the same fact stated
    # elsewhere), so it's read in full here and each tenant's `users`
    # checked in turn under its own TenantContext -- the only correct
    # way to answer "does a platform admin exist anywhere" against an
    # RLS-enforced connection. Cheap for a first-deploy bootstrap, where
    # the tenant count is zero or (on a re-run) very small.
    async with UnitOfWork(session_factory) as uow:
        tenant_ids = (await uow.session.execute(text("SELECT id FROM tenants"))).scalars().all()

    existing_admin: tuple[str, str, str] | None = None
    for tid in tenant_ids:
        async with UnitOfWork(session_factory, TenantContext(tid)) as uow:
            row = (
                await uow.session.execute(
                    text(
                        "SELECT id, email FROM users "
                        "WHERE is_platform_admin = true AND deleted_at IS NULL LIMIT 1"
                    )
                )
            ).first()
        if row is not None:
            existing_admin = (row.id, row.email, tid)
            break

    if existing_admin is not None:
        admin_id, admin_email, admin_tenant_id = existing_admin
        print(
            f"A platform admin already exists: id={admin_id} email={admin_email} tenant_id={admin_tenant_id}"
        )
        print(
            "Nothing to do -- this script only ever creates the first platform admin. "
            "Use services/api/scripts/create_user.py for every account after that."
        )
        await engine.dispose()
        return

    async with UnitOfWork(session_factory) as uow:
        tenant_repo = SQLAlchemyTenantRepository(uow.session)
        existing_tenant = await tenant_repo.get_by_legal_name(_PLATFORM_OPS_LEGAL_NAME)

    if existing_tenant is not None:
        tenant_id = existing_tenant.id
        print(f"Platform Ops tenant already exists: {tenant_id}")
    else:
        if not args.apply:
            print(f"Would provision tenant: {_PLATFORM_OPS_LEGAL_NAME}")
            tenant_id = None
        else:
            provisioning_service = TenantProvisioningService(
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
                token_service=JWTTokenService(
                    private_key=settings.jwt.private_key,
                    public_key=settings.jwt.public_key,
                    issuer=settings.jwt.issuer,
                    access_ttl_seconds=settings.jwt.access_ttl_seconds,
                ),
                outbox_writer_factory=SQLAlchemyOutboxWriter,
            )
            tenant, _owner, _raw_activation_token = await provisioning_service.provision(
                legal_name=_PLATFORM_OPS_LEGAL_NAME,
                display_name=_PLATFORM_OPS_DISPLAY_NAME,
                default_currency_code="USD",
                owner_email=_PLATFORM_OPS_OWNER_EMAIL_PLACEHOLDER,
            )
            tenant_id = tenant.id
            print(f"Created Platform Ops tenant: {tenant_id}")

    password = args.password or _generate_password()

    print(f"\nEmail:    {args.email}")
    print(f"Tenant:   {_PLATFORM_OPS_LEGAL_NAME} ({tenant_id or '(not yet created)'})")

    if not args.apply:
        print("\nDry run (no --apply passed). Would:")
        print(f"  - create an active, is_platform_admin=true user with email {args.email}")
        if not args.password:
            print("  - generate a random password (shown only when --apply is actually passed)")
        await engine.dispose()
        return

    assert tenant_id is not None
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        uow.session.add(
            UserModel(
                id=generate_ulid(),
                tenant_id=tenant_id,
                email=args.email,
                phone=None,
                password_hash=Argon2PasswordHasher().hash(password),
                pin_hash=None,
                permission_version=1,
                status="active",
                is_platform_admin=True,
                created_at=datetime.now(UTC),
            )
        )
        await uow.session.flush()

    await engine.dispose()

    print(f"\nCreated platform admin: {args.email}")
    if not args.password:
        print(f"\nGenerated password (shown once, not stored or logged): {password}")
    print(f"\ntenantId for login: {tenant_id}")
    print(
        "POST /api/v1/auth/login requires tenantId in the body (auth_schemas.py) -- "
        "this platform admin belongs to the Platform Ops tenant above like any other "
        "user, it just also carries is_platform_admin=true."
    )
    print(
        "\nHand the email/password/tenantId to whoever will use them, over a channel "
        "you trust -- do not paste them back into this terminal's scrollback history or "
        "any chat log. Log in, then call POST /api/v1/admin/tenants with the resulting "
        "bearer token to create the first real hotel/restaurant tenant."
    )


if __name__ == "__main__":
    asyncio.run(main())
