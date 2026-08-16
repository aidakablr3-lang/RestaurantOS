"""Standalone, manually-run permanent data purge for an already-offboarded
tenant.

**Why this exists.** `POST /api/v1/admin/tenants/{id}/offboard`
(`OffboardTenantUseCase`) is a lifecycle transition only -- it flips the
tenant's status to `offboarded` and revokes sessions, but its own
docstring says plainly that the scheduled, audited physical purge after
the legal retention window is "a background job, not an API call, and
not built in this sprint." Until that job exists, there is no supported
way to permanently remove a real client's data (contract termination,
a data-retention/right-to-erasure request) short of an engineer running
scoped SQL by hand -- which is exactly what this script formalizes into
a single, reviewable, dry-run-by-default tool, instead of a one-off
query improvised under time pressure.

**Deliberately a script, not an API endpoint.** Unlike
`create_user.py` (closes a *capability* gap other tenants' staff can
safely use once a real API exists), this operation is irreversible and
tenant-destroying by design -- exposing it over HTTP, even behind
`require_platform_admin`, would mean a single compromised admin token,
a misclick in a future admin-web page, or a buggy script looping over
tenant ids could permanently destroy a real client's business data with
no confirmation step in between. Kept as an operator-run script so a
human has to deliberately construct and review the exact command before
anything is deleted.

**What this script deliberately does NOT do:**
  - It never purges an `active`/`provisioning`/`suspended`/`migrating`
    tenant. The tenant must already be `offboarded`
    (`POST .../offboard`) -- this is checked live against the database,
    not trusted from the caller.
  - It never guesses which tenant you mean. Beyond `--tenant-id`, you
    must also pass `--confirm-legal-name` matching that tenant's exact
    `legal_name` as stored -- the same "know the name, not just the id"
    confirmation pattern a destructive action in a real UI would use,
    adapted for a CLI with no click-through dialog to provide it.
  - It never hard-codes the list of tenant-scoped tables. It discovers
    every table with a `tenant_id` column from `information_schema` at
    run time, so a future migration that adds a new tenant-scoped table
    is covered automatically -- a hard-coded list is exactly the kind
    of thing that silently goes stale and leaves orphaned data behind
    after a "purge" that is supposed to guarantee none remains.
  - It never runs automatically -- no scheduler, migration hook, or
    app-startup call to this script exists anywhere in this codebase.
  - By default (no `--apply`) it only prints the tenant's identity and
    a per-table row count of what *would* be deleted, and changes
    nothing. You must pass `--apply` to actually delete anything.

**Concurrency-safety mechanism.** All deletes and the final row-count
verification happen inside one transaction (`UnitOfWork`): if any table
still has rows for this tenant after every table's delete pass
converges (which would mean a table exists that no delete pass could
ever clear -- e.g. a genuine bug in this script, or a row inserted
concurrently mid-purge), the whole transaction raises and rolls back --
nothing is left half-deleted. The same table-name list discovered
up front is used for both the delete passes and the final verification
pass, so the two can never silently drift apart.

Usage:
    # Preview only -- no writes, shows exactly what would be deleted:
    DATABASE_URL=postgresql+asyncpg://... python scripts/purge_tenant.py \\
        --tenant-id 01ABC... --confirm-legal-name "Acme Restaurants LLC"

    # Actually purge:
    DATABASE_URL=postgresql+asyncpg://... python scripts/purge_tenant.py \\
        --tenant-id 01ABC... --confirm-legal-name "Acme Restaurants LLC" --apply

Not safe to re-run in the sense of "undo" -- there is no undo. It *is*
safe to run twice by accident: the second run finds the tenant already
gone and exits cleanly with nothing left to do.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from restaurant_os_api.core.config import get_settings
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_MAX_PASSES = 15


async def _discover_tenant_scoped_tables(session: AsyncSession) -> list[str]:
    result = await session.execute(
        text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'tenant_id' "
            "ORDER BY table_name"
        )
    )
    return [row[0] for row in result.all()]


async def _row_counts(
    session: AsyncSession, tenant_id: str, tables: list[str]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables:
        result = await session.execute(
            text(f'SELECT count(*) FROM "{table}" WHERE tenant_id = :tenant_id'),
            {"tenant_id": tenant_id},
        )
        count = result.scalar_one()
        if count:
            counts[table] = count
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tenant-id", required=True, help="ULID of the tenant to purge.")
    parser.add_argument(
        "--confirm-legal-name",
        required=True,
        help="The tenant's exact legal_name, as stored -- refuses to run on a mismatch. "
        "The same 'know the name, not just the id' confirmation a real destructive-action "
        "dialog would require.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete everything. Without this flag, only previews what would happen.",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with UnitOfWork(session_factory, TenantContext(args.tenant_id)) as uow:
        tenant_row = (
            await uow.session.execute(
                text("SELECT legal_name, status FROM tenants WHERE id = :tenant_id"),
                {"tenant_id": args.tenant_id},
            )
        ).one_or_none()

        if tenant_row is None:
            print(f"No tenant found with id {args.tenant_id} -- nothing to purge.")
            await engine.dispose()
            return

        legal_name, status = tenant_row
        if legal_name != args.confirm_legal_name:
            raise SystemExit(
                f"--confirm-legal-name '{args.confirm_legal_name}' does not match this "
                f"tenant's actual legal_name '{legal_name}'. Refusing to guess -- re-run "
                "with the exact legal_name if this is really the tenant you mean to purge."
            )
        if status != "offboarded":
            raise SystemExit(
                f"Tenant '{legal_name}' ({args.tenant_id}) has status '{status}', not "
                "'offboarded'. Purge refuses to run on a tenant that isn't already "
                "offboarded -- call POST /api/v1/admin/tenants/{id}/offboard first."
            )

        tables = await _discover_tenant_scoped_tables(uow.session)
        counts_before = await _row_counts(uow.session, args.tenant_id, tables)

        print(f"Tenant:  {args.tenant_id} ({legal_name})")
        print(f"Status:  {status}")
        print(f"Rows to delete across {len(counts_before)} tenant-scoped tables:")
        for table, count in counts_before.items():
            print(f"  {table}: {count}")
        print("  tenants: 1")

        if not args.apply:
            print("\nDry run (no --apply passed). Nothing was deleted.")
            await engine.dispose()
            return

        pass_num = 0
        while True:
            pass_num += 1
            if pass_num > _MAX_PASSES:
                raise SystemExit(
                    f"Purge did not converge after {_MAX_PASSES} passes -- aborting, "
                    "nothing committed. This likely means a tenant-scoped table has a "
                    "foreign key this script's table-by-table delete can never satisfy; "
                    "needs a human to investigate, not a blind retry."
                )
            deleted_this_pass = 0
            for table in tables:
                # Each table's delete runs inside its own SAVEPOINT
                # (begin_nested): a foreign-key violation only rolls back
                # to that savepoint, not the whole transaction, so the
                # rows this pass already deleted from other tables
                # survive -- expected when this table still has
                # dependents in another tenant-scoped table not yet
                # cleared this pass, the same convergence pattern
                # proven during the zero-to-live rehearsal's own cleanup.
                try:
                    async with uow.session.begin_nested():
                        result = await uow.session.execute(
                            text(f'DELETE FROM "{table}" WHERE tenant_id = :tenant_id'),
                            {"tenant_id": args.tenant_id},
                        )
                except IntegrityError:
                    continue
                if result.rowcount:
                    deleted_this_pass += result.rowcount
                    print(f"  pass {pass_num}: deleted {result.rowcount} from {table}")
            if deleted_this_pass == 0:
                break

        remaining = await _row_counts(uow.session, args.tenant_id, tables)
        if remaining:
            raise SystemExit(
                f"After {pass_num} passes, these tables still have rows for this tenant: "
                f"{remaining} -- aborting, nothing committed."
            )

        await uow.session.execute(
            text("DELETE FROM tenants WHERE id = :tenant_id"), {"tenant_id": args.tenant_id}
        )

        print(f"\nPurged tenant {args.tenant_id} ({legal_name}) -- all data permanently removed.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
