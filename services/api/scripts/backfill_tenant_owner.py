"""Standalone, manually-run backfill for tenants that predate the RBAC
Foundation (Sprint 5 Step 2, Commit 7): grant one specific, named user
the "Tenant Owner" role for one specific, named tenant.

**Why this exists.** `TenantProvisioningService.provision()` now seeds
the SS6.3 default role catalogue for every *new* tenant, but it creates
no `UserRole` grant -- provisioning happens before any user exists
(`OnboardTenantUseCase` takes no user information). Every tenant
provisioned *before* this change also has zero `Role`/`UserRole` rows.
RBAC_Foundation_Architecture.md SS15 states plainly that which existing
user should become a pre-existing tenant's "Tenant Owner" is **not
mechanically derivable** from anything in today's schema -- there is no
"owner" flag distinct from `is_platform_admin`. This script does not
try to guess. It requires both ids as explicit arguments, every time.

**What this script deliberately does NOT do:**
  - It never selects a "default" or "first" user for a tenant.
  - It never runs automatically -- there is no scheduler, migration
    hook, or app-startup call to this script anywhere in this codebase.
  - By default (no `--apply`) it only prints what it *would* do and
    changes nothing. You must pass `--apply` to write.

**Authorization note.** This grant bypasses `RoleGrantPolicy` on
purpose: the policy exists to stop an *already-privileged* user from
escalating themselves or others, but a tenant with zero roles has no
`roles.assign` holder to run the check against in the first place --
that's exactly the bootstrapping gap this script closes. Treat running
it as an operational/administrative action, not an API call; it should
be run by someone who already has out-of-band authority to make this
decision for the tenant (e.g. platform ops during a support ticket),
the same trust level `scripts/seed_e2e_fixtures.py` already assumes for
direct-to-database fixture writes.

Usage:
    # Preview only -- no writes:
    DATABASE_URL=postgresql+asyncpg://... python scripts/backfill_tenant_owner.py \\
        --tenant-id 01ABC... --user-id 01XYZ...

    # Actually grant it:
    DATABASE_URL=postgresql+asyncpg://... python scripts/backfill_tenant_owner.py \\
        --tenant-id 01ABC... --user-id 01XYZ... --apply

Safe to re-run: if the user already holds Tenant Owner, it reports that
and makes no further change.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from restaurant_os_api.core.config import get_settings
from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.services import seed_default_roles
from restaurant_os_api.modules.identity.domain.entities import UserRole
from restaurant_os_api.modules.identity.domain.events import UserRoleAssigned
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyRolePermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
    SQLAlchemyUserRoleRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

_TENANT_OWNER_ROLE_NAME = "Tenant Owner"


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tenant-id", required=True, help="ULID of the tenant to backfill.")
    parser.add_argument(
        "--user-id",
        required=True,
        help="ULID of the user to grant Tenant Owner to. Must already belong to --tenant-id.",
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

    async with UnitOfWork(session_factory, TenantContext(args.tenant_id)) as uow:
        tenant_repo = SQLAlchemyTenantRepository(uow.session)
        user_repo = SQLAlchemyUserRepository(uow.session)
        role_repo = SQLAlchemyRoleRepository(uow.session)
        user_role_repo = SQLAlchemyUserRoleRepository(uow.session)

        tenant = await tenant_repo.get_by_id(args.tenant_id)
        if tenant is None:
            raise SystemExit(f"No tenant found with id {args.tenant_id}")

        user = await user_repo.get_by_id(args.tenant_id, args.user_id)
        if user is None:
            raise SystemExit(
                f"No user found with id {args.user_id} belonging to tenant {args.tenant_id}"
            )

        owner_role = await role_repo.get_by_name(args.tenant_id, _TENANT_OWNER_ROLE_NAME)
        roles_need_seeding = owner_role is None
        if roles_need_seeding:
            _, existing_role_count = await role_repo.list_for_tenant(
                args.tenant_id, offset=0, limit=1
            )
            if existing_role_count > 0:
                # The tenant has *some* roles but no role literally named
                # "Tenant Owner" -- an ambiguous, non-default state (e.g.
                # a hand-edited catalogue). Refusing rather than guessing
                # or silently adding a 7-role default catalogue on top.
                raise SystemExit(
                    f"Tenant {args.tenant_id} already has {existing_role_count} role(s) but "
                    f"none named '{_TENANT_OWNER_ROLE_NAME}'. Refusing to guess -- resolve "
                    "manually (create the role via POST /api/v1/rbac/roles once someone holds "
                    "roles.assign, or inspect the existing catalogue)."
                )

        already_owner = False
        if owner_role is not None:
            already_owner = await user_role_repo.exists(
                args.tenant_id, args.user_id, owner_role.id, branch_id=None
            )

        print(f"Tenant:            {tenant.id} ({tenant.legal_name})")
        print(f"User:              {user.id} ({user.email})")
        print(f"Roles need seeding: {roles_need_seeding}")
        print(f"Already Tenant Owner: {already_owner}")

        if already_owner:
            print("\nNothing to do -- user already holds Tenant Owner tenant-wide.")
            return

        if not args.apply:
            print("\nDry run (no --apply passed). Would:")
            if roles_need_seeding:
                print("  - seed the 7 default SS6.3 roles for this tenant")
            print(f"  - grant '{_TENANT_OWNER_ROLE_NAME}' to user {args.user_id}, tenant-wide")
            print("  - bump the user's permission_version")
            return

        now = datetime.now(UTC)

        if roles_need_seeding:
            seeded = await seed_default_roles(
                role_repo=role_repo,
                role_permission_repo=SQLAlchemyRolePermissionRepository(uow.session),
                outbox=SQLAlchemyOutboxWriter(uow.session),
                tenant_id=args.tenant_id,
                now=now,
            )
            owner_role = seeded[_TENANT_OWNER_ROLE_NAME]
            print(f"Seeded {len(seeded)} default roles.")

        assert owner_role is not None  # narrowed above: seeded or pre-existing

        user_role = await user_role_repo.create(
            UserRole(
                id=generate_ulid(),
                tenant_id=args.tenant_id,
                user_id=args.user_id,
                role_id=owner_role.id,
                branch_id=None,
                granted_at=now,
                granted_by_user_id=None,  # manual backfill, no acting granter -- see module docstring
            )
        )
        await user_repo.bump_permission_version(args.tenant_id, args.user_id)
        await SQLAlchemyOutboxWriter(uow.session).publish(
            args.tenant_id,
            UserRoleAssigned(
                user_role_id=user_role.id,
                user_id=args.user_id,
                role_id=owner_role.id,
                branch_id=None,
                granted_by_user_id=None,
                occurred_at=now,
            ),
        )

        print(f"\nGranted Tenant Owner (user_role_id={user_role.id}).")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
