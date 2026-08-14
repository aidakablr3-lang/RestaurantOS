"""RestaurantOS Pilot Deployment Smoke Test.

Executes the automated checks from docs/RestaurantOS_Pilot_Deployment_Checklist.md
against a real running instance. Built directly in response to the Run 4
simulation's own incident: a stale backend process served pre-fix code for
an extended period, undetected until a manual OpenAPI inspection caught it.
Item 7/18 below re-run that exact check automatically.

This script performs REAL HTTP calls against a REAL running API and creates
a REAL test order/bill/payment (item 15-19). Do not point it at a database
with real guest data unless you are prepared for that test transaction to
exist afterward -- see checklist item 22.

Usage:
    python scripts/pilot_smoke_test.py \\
        --base-url http://localhost:8000 \\
        --database-url "postgresql://user@host:port/dbname" \\
        --tenant-id <ulid> --branch-id <ulid> --table-id <ulid> \\
        --menu-item-id <ulid> --email staff@example.com --password '...'

Every ID argument is optional; when omitted, the corresponding checks that
need it are skipped (reported as SKIP, not FAIL) rather than guessing.
Exit code is 0 only if every executed check passed.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from dataclasses import dataclass, field
from decimal import Decimal

import httpx

try:
    import asyncpg
except ImportError:  # pragma: no cover - asyncpg is a project dependency already
    asyncpg = None  # type: ignore[assignment]


@dataclass
class Results:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def ok(self, item: str, detail: str = "") -> None:
        self.passed.append(item)
        print(f"[PASS] {item}" + (f" -- {detail}" if detail else ""))

    def fail(self, item: str, detail: str) -> None:
        self.failed.append(item)
        print(f"[FAIL] {item} -- {detail}")

    def skip(self, item: str, detail: str) -> None:
        self.skipped.append(item)
        print(f"[SKIP] {item} -- {detail}")


async def check_database(results: Results, database_url: str | None) -> None:
    if not database_url:
        results.skip("1/2. PostgreSQL availability + connection", "--database-url not supplied")
        return
    if asyncpg is None:
        results.skip(
            "1/2. PostgreSQL availability + connection", "asyncpg not installed in this environment"
        )
        return
    # asyncpg needs a plain postgresql:// DSN, not the SQLAlchemy +asyncpg form.
    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncpg.connect(dsn, timeout=5)
        await conn.fetchval("SELECT 1")
        await conn.close()
        results.ok("1/2. PostgreSQL availability + connection")
    except Exception as exc:  # noqa: BLE001 - report any connection failure as a smoke-test finding
        results.fail("1/2. PostgreSQL availability + connection", str(exc))


def check_alembic(results: Results) -> None:
    try:
        # `sys.executable -m alembic`, not a bare `alembic` on PATH: this
        # script is routinely invoked as `path/to/venv/python.exe
        # pilot_smoke_test.py`, which does not put that same venv's
        # Scripts/bin directory on subprocess PATH -- bare "alembic" then
        # resolves to whatever (if anything) is globally on PATH, not
        # necessarily this environment's alembic. -m guarantees the same
        # interpreter/environment already running this script.
        current = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        heads = subprocess.run(
            [sys.executable, "-m", "alembic", "heads"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if current.returncode != 0 or heads.returncode != 0:
            results.fail(
                "3. Alembic migration state",
                f"alembic exited non-zero: {current.stderr or heads.stderr}",
            )
            return
        current_rev = current.stdout.strip().split()[0] if current.stdout.strip() else ""
        head_rev = heads.stdout.strip().split()[0] if heads.stdout.strip() else ""
        if current_rev and head_rev and current_rev == head_rev:
            results.ok("3. Alembic migration state", f"at head ({current_rev})")
        else:
            results.fail(
                "3. Alembic migration state",
                f"current={current_rev!r} heads={head_rev!r} -- not at head",
            )
    except FileNotFoundError:
        results.skip(
            "3. Alembic migration state",
            "alembic module not importable by this interpreter",
        )
    except Exception as exc:  # noqa: BLE001
        results.fail("3. Alembic migration state", str(exc))


async def check_health(client: httpx.AsyncClient, results: Results) -> bool:
    try:
        r = await client.get("/health/live")
        if r.status_code == 200 and r.json().get("status") == "ok":
            results.ok("5/8. Backend startup + health check")
            return True
        results.fail("5/8. Backend startup + health check", f"status={r.status_code} body={r.text}")
        return False
    except Exception as exc:  # noqa: BLE001
        results.fail("5/8. Backend startup + health check", f"could not reach --base-url: {exc}")
        return False


async def check_openapi(client: httpx.AsyncClient, results: Results) -> None:
    try:
        r = await client.get("/openapi.json")
        if r.status_code != 200:
            results.fail("7. OpenAPI verification", f"GET /openapi.json returned {r.status_code}")
            return
        schema = r.json()
        paths = schema.get("paths", {})

        refund_path = paths.get("/api/v1/payments/{payment_id}/refund")
        if refund_path is not None:
            results.fail(
                "7. OpenAPI verification",
                "POST /payments/{id}/refund is STILL PRESENT in the live schema -- this route was "
                "deliberately retired. The running process is almost certainly serving stale/old code "
                "(this is the exact symptom that caused the Run 4 simulation's false negative). "
                "Restart the backend before doing anything else.",
            )
            return

        operation_count = sum(len(methods) for methods in paths.values())
        if operation_count < 50:
            results.fail(
                "7. OpenAPI verification",
                f"only {operation_count} operations found -- suspiciously low, some routers may have "
                "failed to register.",
            )
            return

        results.ok(
            "7. OpenAPI verification",
            f"{operation_count} operations, refund route correctly absent",
        )
    except Exception as exc:  # noqa: BLE001
        results.fail("7. OpenAPI verification", str(exc))


async def check_auth(
    client: httpx.AsyncClient,
    results: Results,
    tenant_id: str | None,
    email: str | None,
    password: str | None,
) -> str | None:
    if not (tenant_id and email and password):
        results.skip("9. Authentication test", "--tenant-id/--email/--password not all supplied")
        return None
    try:
        r = await client.post(
            "/api/v1/auth/login", json={"tenantId": tenant_id, "email": email, "password": password}
        )
        if r.status_code != 200:
            results.fail("9. Authentication test", f"login returned {r.status_code}: {r.text}")
            return None
        token = r.json()["data"]["accessToken"]
        results.ok("9. Authentication test")
        return token
    except Exception as exc:  # noqa: BLE001
        results.fail("9. Authentication test", str(exc))
        return None


async def check_rbac(
    client: httpx.AsyncClient, results: Results, token: str | None, branch_id: str | None
) -> None:
    if not (token and branch_id):
        results.skip("10. RBAC smoke test", "requires a token (item 9) and --branch-id")
        return
    try:
        auth = {"Authorization": f"Bearer {token}"}
        positive = await client.get(
            f"/api/v1/branches/{branch_id}/orders?offset=0&limit=1", headers=auth
        )
        no_auth = await client.get(f"/api/v1/branches/{branch_id}/orders?offset=0&limit=1")
        if positive.status_code == 200 and no_auth.status_code == 401:
            results.ok(
                "10. RBAC smoke test",
                "authorized call succeeds, unauthenticated call correctly rejected (401)",
            )
        else:
            results.fail(
                "10. RBAC smoke test",
                f"authorized status={positive.status_code} (expected 200), "
                f"unauthenticated status={no_auth.status_code} (expected 401)",
            )
    except Exception as exc:  # noqa: BLE001
        results.fail("10. RBAC smoke test", str(exc))


async def check_restaurant_branch(
    client: httpx.AsyncClient, results: Results, token: str | None, branch_id: str | None
) -> None:
    if not (token and branch_id):
        results.skip("11. Restaurant/branch verification", "requires a token and --branch-id")
        return
    try:
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.get(f"/api/v1/branches/{branch_id}", headers=auth)
        if r.status_code == 200:
            data = r.json()["data"]
            results.ok(
                "11. Restaurant/branch verification", f"branch '{data.get('name')}' resolved"
            )
        else:
            results.fail("11. Restaurant/branch verification", f"status={r.status_code}: {r.text}")
    except Exception as exc:  # noqa: BLE001
        results.fail("11. Restaurant/branch verification", str(exc))


async def check_tables(
    client: httpx.AsyncClient, results: Results, token: str | None, branch_id: str | None
) -> None:
    if not (token and branch_id):
        results.skip("12. Table verification", "requires a token and --branch-id")
        return
    try:
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.get(f"/api/v1/branches/{branch_id}/tables?offset=0&limit=50", headers=auth)
        if r.status_code != 200:
            results.fail("12. Table verification", f"status={r.status_code}: {r.text}")
            return
        tables = r.json()["data"]
        stuck_occupied = [t["tableNumber"] for t in tables if t["status"] == "occupied"]
        if stuck_occupied:
            results.fail(
                "12. Table verification",
                f"{len(tables)} tables found, but these are already 'occupied' before service started "
                f"today: {stuck_occupied} -- confirm this is genuinely expected, not a stuck-table bug.",
            )
        else:
            results.ok(
                "12. Table verification", f"{len(tables)} tables, none unexpectedly occupied"
            )
    except Exception as exc:  # noqa: BLE001
        results.fail("12. Table verification", str(exc))


async def check_menu(
    client: httpx.AsyncClient,
    results: Results,
    token: str | None,
    branch_id: str | None,
    tenant_id: str | None,
) -> None:
    if not (token and branch_id):
        results.skip("13. Menu verification", "requires a token and --branch-id")
        return
    try:
        auth = {"Authorization": f"Bearer {token}"}
        # Menu categories are scoped by restaurant_id, not branch_id directly --
        # resolve the branch's own restaurant first.
        r = await client.get(f"/api/v1/branches/{branch_id}", headers=auth)
        if r.status_code != 200:
            results.fail(
                "13. Menu verification",
                f"could not resolve branch to find its restaurant: {r.status_code} {r.text}",
            )
            return
        restaurant_id = r.json()["data"]["restaurantId"]
        r = await client.get(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories?offset=0&limit=50", headers=auth
        )
        if r.status_code != 200:
            results.fail("13. Menu verification", f"status={r.status_code}: {r.text}")
            return
        categories = r.json()["data"]
        if len(categories) == 0:
            results.fail("13. Menu verification", "zero menu categories found for this restaurant")
        else:
            results.ok("13. Menu verification", f"{len(categories)} menu categories found")
    except Exception as exc:  # noqa: BLE001
        results.fail("13. Menu verification", str(exc))


async def check_qr(client: httpx.AsyncClient, results: Results, qr_token: str | None) -> None:
    if not qr_token:
        results.skip("14. QR verification", "--qr-token not supplied")
        return
    try:
        r = await client.get(f"/api/v1/qr/{qr_token}")
        if r.status_code == 200:
            # Deliberately NOT the standard ApiResponse envelope -- ADR 0001
            # and architecture SS7 both specify this bootstrap route's
            # response literally as {tenant_id, branch_id, table_id}, no
            # envelope, no camelCase (see qr_resolution_schemas.py's own
            # docstring). Confirmed live during Phase 1 deployment
            # validation; this check previously assumed the standard
            # envelope shape and always failed once actually exercised
            # with a real --qr-token.
            data = r.json()
            results.ok(
                "14. QR verification",
                f"resolved to table_id '{data.get('table_id')}'",
            )
        else:
            results.fail("14. QR verification", f"status={r.status_code}: {r.text}")
    except Exception as exc:  # noqa: BLE001
        results.fail("14. QR verification", str(exc))


async def check_order_kds_payment_release_eod(
    client: httpx.AsyncClient,
    results: Results,
    token: str | None,
    branch_id: str | None,
    table_id: str | None,
    menu_item_id: str | None,
) -> None:
    if not (token and branch_id and table_id and menu_item_id):
        results.skip(
            "15-19. Test order / KDS / payment / table release / EOD report",
            "requires a token, --branch-id, --table-id, and --menu-item-id",
        )
        return
    auth = {"Authorization": f"Bearer {token}"}
    try:
        r = await client.post(
            f"/api/v1/branches/{branch_id}/orders",
            json={"orderSource": "pos", "tableId": table_id},
            headers=auth,
        )
        if r.status_code != 201:
            results.fail("15. Test order", f"create failed: {r.status_code} {r.text}")
            return
        order_id = r.json()["data"]["id"]
        r = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={"menuItemId": menu_item_id, "quantity": 1, "modifiersSnapshot": []},
            headers=auth,
        )
        if r.status_code != 201:
            results.fail("15. Test order", f"add item failed: {r.status_code} {r.text}")
            return
        r = await client.post(f"/api/v1/orders/{order_id}/fire", headers=auth)
        if r.status_code != 200:
            results.fail("15. Test order", f"fire failed: {r.status_code} {r.text}")
            return
        r = await client.get(f"/api/v1/branches/{branch_id}/tables?offset=0&limit=50", headers=auth)
        table_status = next((t["status"] for t in r.json()["data"] if t["id"] == table_id), None)
        if table_status != "occupied":
            results.fail(
                "15. Test order",
                f"table status after fire is {table_status!r}, expected 'occupied'",
            )
            return
        results.ok("15. Test order", f"order {order_id} created and fired, table occupied")

        r = await client.get(
            f"/api/v1/branches/{branch_id}/kitchen-tickets?offset=0&limit=50", headers=auth
        )
        tickets = [t for t in r.json().get("data", []) if t["orderId"] == order_id]
        if not tickets:
            results.fail("16. KDS verification", "no kitchen/bar tickets found for the test order")
        else:
            results.ok("16. KDS verification", f"{len(tickets)} ticket(s) generated")

        r = await client.post(f"/api/v1/orders/{order_id}/bill", headers=auth)
        if r.status_code != 201:
            results.fail("17. Test payment", f"bill generation failed: {r.status_code} {r.text}")
            return
        bill = r.json()["data"]
        amount_due = Decimal(bill["amountDue"])
        r = await client.post(
            f"/api/v1/bills/{bill['id']}/payments",
            json={"tenderType": "cash", "amount": str(amount_due)},
            headers=auth,
        )
        if r.status_code != 201:
            results.fail("17. Test payment", f"payment failed: {r.status_code} {r.text}")
            return
        r = await client.get(f"/api/v1/bills/{bill['id']}", headers=auth)
        if r.json()["data"]["status"] != "closed":
            results.fail(
                "17. Test payment",
                f"bill status after full payment is {r.json()['data']['status']!r}, expected 'closed'",
            )
        else:
            results.ok("17. Test payment", f"bill closed, amount_due was {amount_due}")

        r = await client.get(f"/api/v1/branches/{branch_id}/tables?offset=0&limit=50", headers=auth)
        table_status_after = next(
            (t["status"] for t in r.json()["data"] if t["id"] == table_id), None
        )
        if table_status_after == "available":
            results.ok(
                "18. Automatic table release", "table auto-released with no manual status call"
            )
        else:
            results.fail(
                "18. Automatic table release",
                f"table status after full payment is {table_status_after!r}, expected 'available'. "
                "This is the exact P0 class of bug Run 4 caught -- check item 7 (OpenAPI/stale process) first.",
            )

        import datetime as _dt

        today = _dt.datetime.now(_dt.UTC).date().isoformat()
        r = await client.get(
            f"/api/v1/branches/{branch_id}/reports/end-of-day?date={today}", headers=auth
        )
        if r.status_code == 200:
            results.ok("19. EOD report", f"orderCount={r.json()['data'].get('orderCount')}")
        else:
            results.fail("19. EOD report", f"status={r.status_code}: {r.text}")

        print(
            f"\n[NOTE] Test order {order_id} / bill {bill['id']} were created for real by this smoke "
            "test (checklist item 22) -- exclude or annotate them before the pilot's own first-day "
            "reconciliation."
        )
    except Exception as exc:  # noqa: BLE001
        results.fail("15-19. Test order / KDS / payment / table release / EOD report", str(exc))


def print_manual_reminders() -> None:
    print("\n--- MANUAL checklist items (not automated by this script) ---")
    print("[ ] 4. Environment variables set as real process env vars (see checklist doc)")
    print("[ ] 6. Frontend production build points at the correct API base URL")
    print("[ ] 20. Backup job confirmed running / tested restore procedure exists")
    print("[ ] 21. Rollback/recovery procedure documented and on-call person identified")
    print(
        "[ ] 22. Confirm handling of this run's own test order/bill (see NOTE above, if item 15 ran)"
    )


async def main_async(args: argparse.Namespace) -> int:
    results = Results()

    await check_database(results, args.database_url)
    check_alembic(results)

    async with httpx.AsyncClient(base_url=args.base_url, timeout=15) as client:
        healthy = await check_health(client, results)
        if not healthy:
            print("\nBackend is not reachable -- skipping all remaining HTTP-dependent checks.")
            print_manual_reminders()
            return 1

        await check_openapi(client, results)
        token = await check_auth(client, results, args.tenant_id, args.email, args.password)
        await check_rbac(client, results, token, args.branch_id)
        await check_restaurant_branch(client, results, token, args.branch_id)
        await check_tables(client, results, token, args.branch_id)
        await check_menu(client, results, token, args.branch_id, args.tenant_id)
        await check_qr(client, results, args.qr_token)
        await check_order_kds_payment_release_eod(
            client, results, token, args.branch_id, args.table_id, args.menu_item_id
        )

    print_manual_reminders()

    print(
        f"\n--- SUMMARY: {len(results.passed)} passed, {len(results.failed)} failed, {len(results.skipped)} skipped ---"
    )
    if results.failed:
        print("FAILED CHECKS:")
        for item in results.failed:
            print(f"  - {item}")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base-url", required=True, help="Base URL of the running API, e.g. http://localhost:8000"
    )
    parser.add_argument(
        "--database-url", default=None, help="Postgres connection string (SQLAlchemy or plain form)"
    )
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument("--branch-id", default=None)
    parser.add_argument(
        "--table-id", default=None, help="A table currently 'available', used for the test order"
    )
    parser.add_argument("--menu-item-id", default=None)
    parser.add_argument("--qr-token", default=None)
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
