# End-to-end tests (Playwright)

Automates the 7 Tenant Administration flows Sprint 4.1 Step 3 verified by
hand in a browser: Login, Tenant List, Tenant Details, Create Tenant,
Edit Tenant, Suspend Tenant, Reactivate Tenant.

## One-time setup

This suite drives a real browser against a real `services/api` +
PostgreSQL backend -- it does not mock anything. Get that stack running
first (see the root `docs/AI_HANDOFF.md` §17 for the full from-scratch
sequence: installing Postgres, migrating, generating a JWT keypair,
starting `uvicorn`), then seed the fixed E2E admin fixture:

```bash
cd services/api
DATABASE_URL=<your dev database URL> python scripts/seed_e2e_fixtures.py
```

This prints a `tenantId` -- export it (and the API's URL, if not the
default) so Playwright can find the same fixture:

```bash
export E2E_ADMIN_TENANT_ID=<the tenantId the script printed>
export E2E_API_BASE_URL=http://localhost:8000   # only if not the default
```

`E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` default to the script's own
fixed credentials (`e2e-admin@restaurantos.dev` / `E2EAdmin!2026`) and
don't need to be set unless you changed them in the script.

## Running

```bash
npm run e2e        # headless, once
npm run e2e:ui      # interactive UI mode, for writing/debugging specs
```

`playwright.config.ts` starts `admin-web`'s own dev server automatically
(on port 3100 by default, to avoid colliding with a `npm run dev` you
already have open on 3000) and points `NEXT_PUBLIC_API_BASE_URL` at
whatever `E2E_API_BASE_URL` resolves to. It does **not** start Postgres
or `services/api` -- `global-setup.ts` checks the backend is reachable
and the E2E fixture logs in successfully before any spec runs, and
fails with a clear message (not 20 confusing per-test failures) if not.

## Design notes

- Every spec logs in through the real login form (`fixtures.ts`'s
  `loginViaUi`) rather than injecting a token into `localStorage` --
  Login is one of the flows this suite has to cover, so bypassing it
  in every other spec's setup would silently stop testing it after
  `login.spec.ts`.
- Specs that need a tenant to act on create their own via the real
  Create Tenant form (`createTenantViaUi`) instead of depending on
  whatever a previous run left in the shared dev database -- this
  suite doesn't reset that database between runs (only the backend's
  own integration-test database, a separate one, gets truncated between
  test runs -- see `services/api/tests/integration/conftest.py`).
- `workers: 1` / `fullyParallel: false`: specs share one seeded admin
  and one real database; running them concurrently would make
  list/pagination assertions flaky against each other's fixture data.
