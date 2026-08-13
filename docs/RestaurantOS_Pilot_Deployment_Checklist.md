# RestaurantOS — Pilot Deployment Checklist

**Purpose:** prevent a repeat of the Run 4 incident — a backend process left running old code after a fix was deployed, undetected until a manual OpenAPI inspection caught it. Run this checklist (and the companion smoke test, `scripts/pilot_smoke_test.py`) after **every** deploy, restart, or environment change during the pilot, not just at initial go-live.

Each item states what to check, how to check it, and what a pass/fail looks like. Items marked **[AUTOMATED]** are covered by `scripts/pilot_smoke_test.py`; items marked **[MANUAL]** require a human decision or an action outside what a smoke test can safely automate.

---

### 1. PostgreSQL availability — **[AUTOMATED]**
Confirm the target Postgres instance is up and accepting connections on the expected host/port before starting the API. `pg_isready -h <host> -p <port>`, or the smoke test's own connection check.

### 2. Database connection — **[AUTOMATED]**
Confirm the API can actually authenticate and connect using the exact `DATABASE_URL` it will run with — not a developer's own working `.env`. Remember `DatabaseSettings` does **not** read `.env` for this value (P1-3 in the Pilot Readiness Review) — it must be a real process/shell environment variable.

### 3. Alembic migration state — **[AUTOMATED]**
Run `alembic current` and `alembic heads` from `services/api/`; they must match. A database behind the code's expected schema will fail in confusing, hard-to-diagnose ways rather than a clean error.

### 4. Environment variables — **[MANUAL, checklist below]**
Confirm every required variable is set as a real process/shell environment variable (not just present in a `.env` file that nothing reads):
- `DATABASE_URL` (full `postgresql+asyncpg://` URL)
- `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` — **real PEM content**, not a file path, not the `dummy`/`x` placeholder values that only satisfy pytest's own fixture-overridden `TokenService`
- `CORS_ALLOWED_ORIGINS` — must include the exact origin the pilot's frontend will actually be served from
- `APP_ENV` set appropriately (not left at a dev default in a pilot deployment)

### 5. Backend startup — **[AUTOMATED]**
Start uvicorn, wait for a successful bind, then confirm `GET /health/live` returns `{"status": "ok"}`.

### 6. Frontend startup/build — **[MANUAL]**
Run a production build (`next build`) rather than relying on a dev server for the pilot. Confirm the build completes cleanly and the resulting app points at the correct API base URL for the pilot environment (not `localhost`).

### 7. OpenAPI verification — **[AUTOMATED]** — *the check that would have caught Run 4's incident*
Fetch `GET /openapi.json` from the **running** process and check it against what the **current source code** actually defines:
- The retired refund route (`POST /payments/{id}/refund`) must be **absent**.
- The operation count should be sane (the codebase's own test suite pins an exact expected count in `tests/unit/test_main.py` — cross-reference it).
If the schema doesn't match what the source defines, the running process is stale. Restart it before doing anything else.

### 8. Health check — **[AUTOMATED]**
`GET /health/live` → `200 {"status": "ok"}`.

### 9. Authentication test — **[AUTOMATED]**
`POST /api/v1/auth/login` with a real, known pilot-environment user. Must return a valid access token. A failure here usually means the JWT keys aren't loaded correctly (see item 4).

### 10. RBAC smoke test — **[AUTOMATED]**
Using the token from item 9, confirm: (a) an action the logged-in role IS authorized for succeeds; (b) an action it is NOT authorized for returns `403`, not a silent success or a crash.

### 11. Restaurant/branch verification — **[AUTOMATED]**
`GET` the pilot restaurant and branch by ID; confirm they resolve and their names/status match what's expected for this deployment (catches "pointed at the wrong database" mistakes early).

### 12. Table verification — **[AUTOMATED]**
List tables for the branch; confirm the expected zones/table numbers are present and every table's status is sane (no table should already be `occupied` at the start of a fresh pilot day unless that's genuinely expected).

### 13. Menu verification — **[AUTOMATED]**
List menu categories/items for the branch; confirm the count is non-zero and spot-check that prices are what's expected (a currency or decimal mistake here is a real financial risk).

### 14. QR verification — **[AUTOMATED, if QR is in use for the pilot]**
Resolve at least one real QR token via `GET /api/v1/qr/{token}` and confirm it returns the correct table/branch/menu.

### 15. Test order — **[AUTOMATED]**
Create one real order against a real table via the API, add one real menu item, and fire it. Confirm the table's status flips to `occupied`.

### 16. KDS verification — **[AUTOMATED]**
Confirm the fired order produced at least one real kitchen/bar ticket, retrievable via the kitchen-tickets endpoint.

### 17. Test payment — **[AUTOMATED]**
Generate a bill for the test order and record a payment for exactly `amountDue`. Confirm the bill closes.

### 18. Automatic table release — **[AUTOMATED]** — *the specific behavior Run 4's critical test covers*
After the test payment in item 17, confirm the table's status is back to `available` **without any manual table-status call having been made**. If it isn't, do not proceed — this is the exact P0 class of bug the Run 4 simulation caught, and its presence means either the code has regressed or (as in Run 4) the running process is stale (re-check item 7).

### 19. EOD report — **[AUTOMATED]**
Call the end-of-day report endpoint for the current date; confirm it returns without error and that the test order/payment from items 15-18 appear in its totals.

### 20. Backup verification — **[MANUAL]**
Confirm a working, tested backup mechanism exists for the pilot's Postgres instance (`pg_dump` on a schedule, or the hosting provider's managed backup) **before** the pilot's first live day. A smoke test cannot safely verify "backups work" without either taking a real backup (fine) or attempting a real restore against a non-throwaway database (not something to automate against a live pilot instance). At minimum: confirm the backup job ran today, and confirm someone knows how to invoke a restore.

### 21. Rollback / recovery procedure — **[MANUAL]**
Confirm, in writing, before go-live: (a) how to roll the API back to the previous known-good commit/deploy artifact, (b) how to roll an Alembic migration back one step if the most recent migration is implicated in an incident, (c) who is authorized to make that call during the pilot, and (d) how staff should be told to pause operations (e.g., "stop taking new orders, keep serving what's already fired") while a rollback is in progress. This does not need to be elaborate for a controlled pilot, but it must exist and be known to whoever is on call.

### 22. Clean-up of test data — **[MANUAL]**
The smoke test in items 9-19 creates a real test order/bill/payment. Before the pilot's actual first guest is served, either void/close that test order in a way visible as a test transaction, or note its ID so it can be excluded from the pilot's own first-day reconciliation.

---

## Running the smoke test

```bash
cd services/api
python scripts/pilot_smoke_test.py --base-url http://localhost:8000 --database-url "$DATABASE_URL"
```

See the script's own `--help` for the full set of options (tenant/branch/table/menu-item IDs, credentials). It prints a PASS/FAIL line per checklist item above and a final summary; a non-zero exit code means at least one automated check failed. It performs real HTTP calls against a real running instance — do not point it at a production database with real guest data unless you are prepared for the real test order/payment it creates (see item 22).
