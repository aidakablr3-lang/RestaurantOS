"""Standalone, manually-run user creation for a tenant that already exists.

**Why this exists.** No `POST /api/v1/users` endpoint, no `CreateUserUseCase`,
and no admin-web UI exists anywhere in this codebase for creating a user
account — confirmed by grepping every route in the identity module and every
use case that references `UserRepository`. `UserRepository`'s own port
(`domain/ports/user_repository.py`) has no `create()` method at all; the only
place a `User` row has ever been created is `seed_e2e_fixtures.py`'s direct
`UserModel` insert, whose own docstring says plainly: "No user-creation use
case/endpoint exists yet." This script fills that gap the same way
`backfill_tenant_owner.py` fills the "grant Tenant Owner" gap: a real,
manually-run operational tool, not an API route, until a proper
create-user/invite flow is built.

**Scope, deliberately broader than a one-time bootstrap script.** This is
usable any time a tenant needs a new account — the initial Owner, or a
waiter/manager/kitchen-staff hire added later. A tenant's own Owner cannot
create their own staff today (same gap, no self-service path exists) — so
until a real in-app flow ships, *every* new account for *every* tenant goes
through this script, run by whoever operates the platform.

**What this script deliberately does NOT do:**
  - It never guesses a role. `--role-name` must name a role that already
    exists for the tenant (case-sensitive, exact match) -- if it doesn't,
    the script lists what does exist and stops, the same "refuse to guess"
    posture as `backfill_tenant_owner.py`.
  - It never picks a branch. `--branch-id` is optional and unvalidated
    against the role's intended scope (Owner/Manager are typically
    tenant-wide, Waiter/Kitchen Staff typically branch-scoped) -- the dry-run
    output prints exactly what will be granted, tenant-wide or at a specific
    branch, so you catch a mistake before `--apply`, not after.
  - It never runs automatically -- no scheduler, migration hook, or
    app-startup call to this script exists anywhere.
  - By default (no `--apply`) it only prints what it *would* do and changes
    nothing. You must pass `--apply` to write.
  - It never accepts a password as a bare CLI argument by default (shell
    history, process list exposure) -- pass `--password` only if you
    understand that tradeoff; otherwise a random one is generated and
    printed exactly once.

**Authorization note.** Like `backfill_tenant_owner.py`, the role grant this
script performs bypasses `RoleGrantPolicy` on purpose -- that policy exists
to stop an already-privileged *live API caller* from escalating themselves or
others, not to gate an out-of-band operational action taken by someone who
already has authority to make this decision for the tenant (e.g. you,
running this after a client asks you to add a hire). Pass
`--granted-by-user-id` when you know which real user is authorizing the
grant (e.g. the tenant's own Owner asked you to add this hire) for a better
audit trail; omit it and the grant is recorded the same way
`backfill_tenant_owner.py` records a manual backfill (no acting granter).

Usage:
    # Preview only -- no writes:
    DATABASE_URL=postgresql+asyncpg://... python scripts/create_user.py \\
        --tenant-id 01ABC... --email owner@example.com --role-name "Tenant Owner"

    # Actually create, auto-generated password printed once:
    DATABASE_URL=postgresql+asyncpg://... python scripts/create_user.py \\
        --tenant-id 01ABC... --email owner@example.com --role-name "Tenant Owner" --apply

    # Branch-scoped staff, explicit password, known granter:
    DATABASE_URL=postgresql+asyncpg://... python scripts/create_user.py \\
        --tenant-id 01ABC... --email waiter1@example.com --role-name "Waiter" \\
        --branch-id 01XYZ... --password 'Cor r3ctH0rseBatt3ry' \\
        --granted-by-user-id 01OWNER... --apply

Safe to re-run: if a user with this email already exists in the tenant, the
script reports its current state and makes no further change (it does not
attempt to update an existing user's password or role -- that is a separate,
deliberately out-of-scope action; re-run with a different flow if that's
what you actually need).
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from restaurant_os_api.core.config import get_settings
from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.domain.entities import UserRole
from restaurant_os_api.modules.identity.domain.events import UserRoleAssigned
from restaurant_os_api.modules.identity.infrastructure.database.models import UserModel
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyRoleRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
    SQLAlchemyUserRoleRepository,
)
from restaurant_os_api.modules.identity.infrastructure.security import Argon2PasswordHasher
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


def _generate_password() -> str:
    # 16 chars of URL-safe base64 -- ~96 bits of entropy, comfortably
    # above what Argon2id needs to make offline cracking infeasible, and
    # short enough to read aloud/type once during handover.
    return secrets.token_urlsafe(12)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--tenant-id", required=True, help="ULID of the tenant this user belongs to."
    )
    parser.add_argument("--email", required=True, help="Login email, unique within the tenant.")
    parser.add_argument("--phone", default=None, help="Optional phone number.")
    parser.add_argument(
        "--role-name",
        required=True,
        help="Exact name of an existing role for this tenant (e.g. 'Tenant Owner', 'Waiter'). "
        "Must already exist -- this script never creates or guesses a role.",
    )
    parser.add_argument(
        "--branch-id",
        default=None,
        help="ULID of the branch to scope the role grant to. Omit for a tenant-wide grant "
        "(the usual choice for Owner/Manager; branch-scoped is the usual choice for "
        "Waiter/Kitchen Staff -- this script does not enforce that, it only shows you "
        "what you're about to grant).",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Set an explicit password instead of generating one. Avoid for real accounts -- "
        "bare CLI args land in shell history and process listings. Useful for scripted "
        "test-tenant dry runs with a known throwaway password.",
    )
    parser.add_argument(
        "--granted-by-user-id",
        default=None,
        help="ULID of the real user authorizing this grant (e.g. the tenant's Owner, if they "
        "asked you to add this hire), for a better audit trail. Omitted: recorded as no "
        "acting granter, same as backfill_tenant_owner.py's manual-backfill convention.",
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

        existing_user = await user_repo.get_by_email(args.tenant_id, args.email)
        if existing_user is not None:
            print(
                f"User already exists: {existing_user.id} ({existing_user.email}, "
                f"status={existing_user.status.value})"
            )
            print(
                "Nothing to do -- this script does not update an existing user's "
                "password or role. Re-run against a different email, or handle the "
                "update separately."
            )
            return

        role = await role_repo.get_by_name(args.tenant_id, args.role_name)
        if role is None:
            _, total_roles = await role_repo.list_for_tenant(args.tenant_id, offset=0, limit=100)
            available, _ = await role_repo.list_for_tenant(
                args.tenant_id, offset=0, limit=total_roles or 1
            )
            names = ", ".join(sorted(r.name for r in available)) or "(none)"
            raise SystemExit(
                f"No role named '{args.role_name}' exists for tenant {args.tenant_id}. "
                f"Refusing to guess -- available roles: {names}"
            )

        scope = f"branch {args.branch_id}" if args.branch_id else "tenant-wide"
        password = args.password or _generate_password()

        print(f"Tenant:   {tenant.id} ({tenant.legal_name})")
        print(f"Email:    {args.email}")
        print(f"Role:     {role.name} ({role.id}) -- {scope}")
        print(f"Granter:  {args.granted_by_user_id or '(none recorded)'}")

        if not args.apply:
            print("\nDry run (no --apply passed). Would:")
            print(f"  - create an active user with email {args.email}")
            print(f"  - grant '{role.name}' {scope}")
            if not args.password:
                print("  - generate a random password (shown only when --apply is actually passed)")
            return

        now = datetime.now(UTC)
        user_id = generate_ulid()
        password_hash = Argon2PasswordHasher().hash(password)

        uow.session.add(
            UserModel(
                id=user_id,
                tenant_id=args.tenant_id,
                email=args.email,
                phone=args.phone,
                password_hash=password_hash,
                pin_hash=None,
                permission_version=1,
                status="active",
                is_platform_admin=False,
                created_at=now,
            )
        )
        await uow.session.flush()

        user_role = await user_role_repo.create(
            UserRole(
                id=generate_ulid(),
                tenant_id=args.tenant_id,
                user_id=user_id,
                role_id=role.id,
                branch_id=args.branch_id,
                granted_at=now,
                granted_by_user_id=args.granted_by_user_id,
            )
        )
        await SQLAlchemyOutboxWriter(uow.session).publish(
            args.tenant_id,
            UserRoleAssigned(
                user_role_id=user_role.id,
                user_id=user_id,
                role_id=role.id,
                branch_id=args.branch_id,
                granted_by_user_id=args.granted_by_user_id,
                occurred_at=now,
            ),
        )

        print(f"\nCreated user_id={user_id}, granted '{role.name}' ({scope}).")
        if not args.password:
            print(f"\nGenerated password (shown once, not stored or logged): {password}")
        print(
            "\nHand these to the client over a channel you trust -- do not paste the "
            "password back into this terminal's scrollback history or any chat log."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
