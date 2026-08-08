# RestaurantOS — AI Session Handoff Document

**Purpose:** This is the canonical handoff document for every future Claude session working on RestaurantOS. Read this file first, before touching any code, to reconstruct full project context.

**Last updated:** 2026-08-08
**Updated by:** Sprint 5 Step 1 (Restaurant Platform architecture planning, documentation-only) and Step 2 (RBAC Foundation: architecture doc + 8-commit implementation — domain model, migration `0003`, permission resolution, authorization service, privilege-escalation protection, RBAC REST API, provisioning integration, comprehensive test matrix). See §21 for the full record. Everything in §1–§20 below predates Sprint 5 and describes Sprint 4.1 (Tenant Platform), which is unchanged and still merged into `develop`.

---

## 1. Current Sprint

**Sprint 5 — Restaurant Platform** (the second business platform / bounded context). Step 1 (architecture planning) and Step 2 (RBAC Foundation, a prerequisite Step 1's own review identified) are complete — see §21. Restaurant Platform business entities (Restaurant/Branch/Tables/Menu/QR Ordering/POS/Billing/KDS/Inventory/Liquor) have **not** been started; explicit STOP after RBAC Step 2 per the user's instruction.

Sections 1–20 below are unchanged from Sprint 4.1 and describe **Sprint 4.1 — Tenant Platform** (the first business platform; Product Blueprint Phase 1 / Technical Architecture v2.0 `modules/identity` extension), which remains merged into `develop`, untouched by Sprint 5.

## 2. Current Step

**(Sprint 4.1) Step 3 — Frontend implementation: built, browser-verified, fixed up, user-approved as complete.** **Step 4 — Testing: done for this sprint's scope, user-approved as complete.** **Step 5 — Release hardening: done for this sprint's scope, and the branch is now being prepared for a merge readiness review (§9/§10).** `apps/admin-web` has six of the ten originally-scoped screens, verified working in a real browser against a real running `services/api` + PostgreSQL: Tenant List, Tenant Details, Create Tenant, Edit Tenant, Suspend Tenant, Reactivate Tenant. **Scope was deliberately narrowed mid-session** — see the "Scope-down decision" note below and §11 — user-approved. The manually-verified flows are backed by automated tests (17 backend integration tests + a 24-spec Playwright E2E suite), and the whole stack now has committed local dev infrastructure (Docker Compose) and a CI pipeline (GitHub Actions) that runs those same suites automatically — see the Step 5 section in §8.

Sprint 4.1 follows a 5-step gated process, defined explicitly by the user:

| Step | Description | Status |
|---|---|---|
| 1 | Explain implementation plan, wait for approval | Complete — approved, including 3 explicit architecture-compliance decisions (see §11 Known Issues / Decisions) |
| 2 | Implement backend, wait for approval | Complete — 7 commits, approved |
| 3 | Implement frontend, wait for approval | **Complete — user explicitly confirmed "Step 3 is complete" after reviewing the real-backend browser verification results.** 6/10 originally-scoped screens (7 commits, `a76c5a9`→`012bd8b`) |
| 4 | Testing, wait for approval | **Complete — user explicitly confirmed "Step 4 is complete"** (5 commits, `1962a45`→`695ea34`): integration test suite restored + extended, Playwright E2E suite added, both green |
| 5 | Documentation / release hardening, wait for approval | **Complete — user explicitly approved: "The Tenant Platform Release Candidate (RC1) has passed review... Proceed with the merge."** `feature/tenant-platform-frontend` merged into `develop` via merge commit `80fcb9d`, pushed to `origin/develop`. See §20. |

**Scope-down decision (approved by the user):** The original Step 1 plan listed 10 admin-web screens, including Subscription Status, Quota Dashboard, Feature Flag Display, and Tenant Settings. Discovered mid-session: the backend only exposes those four as **self-service** endpoints (`/api/v1/tenants/me/*`), which resolve `tenant_id` from the caller's own JWT and structurally cannot take an admin-selected tenant ID (`self_service_tenant_router.py:1-4`, citing Data Architecture v2.0 §4.1 — tenant scope is never client-asserted). There is no admin-scoped route (e.g. `/api/v1/admin/tenants/{id}/subscription`) — the underlying use cases (`GetSubscriptionStatusUseCase`, `GetTenantQuotaUsageUseCase`, `GetTenantSettingsUseCase`, `ListFeatureFlagsUseCase`) already accept any `tenant_id` and could be wired to one, but that wiring doesn't exist yet. Presented to the user as a STOP with 3 options (add thin admin endpoints now / scope down / decide later); **user chose to scope down, and explicitly reconfirmed "do not add backend endpoints for Subscription, Quota, Feature Flags, or Tenant Settings in this sprint. Treat those as future work"** when giving the Step 4 task. Those 4 screens are deferred, not abandoned — see §11.

**Real-backend browser verification (Step 3 close-out):** Login, Tenant List, Tenant Details, Create Tenant, Edit Tenant, Suspend Tenant, and Reactivate Tenant were all exercised end-to-end in a real browser against a real `services/api` process backed by a real PostgreSQL 17 database (see §16, §17 for how this environment was stood up — it does not exist as committed infrastructure yet). This surfaced 3 real defects (1 backend, 1 backend CORS, 3 frontend), all fixed, each isolated to its own commit. User reviewed and confirmed: **"Approved. Step 3 is complete... The production defects discovered during verification were valid, isolated, corrected, and committed separately."**

**Step 4 — Testing (this session, user-directed):** Scope given explicitly: fix the `conftest.py` fixture issue, restore the integration suite, add backend end-to-end integration tests, add frontend Playwright E2E tests for all 7 flows, target high coverage so the manually-verified flows become reproducible CI tests — **no new application functionality**. All delivered (§8). Along the way, writing and debugging the Playwright suite found **one more real application defect** (not a test bug): visiting an unknown tenant ID silently logged the platform admin all the way out, because the API client treated every 401 response as "this session is dead," when the backend also uses 401 for unrelated business-logic lookups. Fixed, isolated to its own commit, verified via the E2E suite. Not one line of new functionality was added — every change across all 5 Step 4 commits was a test, a test-infrastructure fix, or a correction of something already in scope. User reviewed and confirmed: **"Approved. Step 4 is complete."**

**Step 5 — Release hardening (this session, user-directed):** Scope given explicitly: developer documentation, local development setup, Docker Compose, CI/CD (GitHub Actions), OpenAPI generation, README updates, environment documentation, release checklist — **no new business functionality, do not begin the Restaurant Platform yet**. All delivered (§8). Two pieces of this could not be *live*-tested in this environment and that limitation is disclosed rather than papered over: this environment has no Docker installed, so `docker compose up` itself was never actually run (the Compose file and Dockerfile were reviewed carefully against the manually-reproduced dev stack from §17 instead, and the gap is called out in `docs/DEVELOPMENT.md`); and this repository has no git remote configured, so `.github/workflows/ci.yml` was authored against GitHub Actions' documented syntax and this session's own locally-reproduced equivalent (same commands, same env vars) but never actually executed by GitHub's runners. Everything else in Step 5 — the OpenAPI export script, the developer docs' manual-setup path, the README, the release checklist — was exercised directly. No architecture files were touched; no application code changed except the new `scripts/export_openapi.py` (pure tooling, not a runtime module).

## 3. Current Milestone

Backend for the Tenant Platform is complete, merged to history (not yet to `develop`/`main` — see §9), and has 17 end-to-end integration tests for the admin API, plus the pre-existing integration suite actually runs at all for the first time this sprint (2 more new tests there too). 24 new backend tests added in Step 4 (5 CORS unit + 2 `set_config()` integration + 17 admin-router integration); **84 backend tests total** across the whole codebase, all passing together. Frontend (`apps/admin-web`) is scaffolded (Next.js 15.5.23 App Router, React 19, TypeScript, Tailwind v4, shadcn/ui on Base UI primitives, TanStack Query, Zustand, React Hook Form + Zod) with Tenant List/Details/Create/Edit/Suspend/Reactivate implemented, browser-verified, and covered by a 24-spec Playwright E2E suite (100% passing, confirmed multiple times). 4 of the original 10 screens remain deferred, explicitly confirmed as future work by the user (see §2, §11). As of Step 5, the whole stack also has committed local dev infrastructure (Docker Compose), a generated OpenAPI schema snapshot, a 5-job GitHub Actions CI pipeline (lint, typecheck, backend tests, frontend build, E2E), developer documentation, and a release checklist — the branch is release-hardened and its readiness for merge into `develop` is being presented to the user now (§9).

## 4. Repository Path

```
C:\Users\prash\Documents\RestaurantOS
```

This is both the Git repository root and the monorepo root (`services/api`, `apps/`, `packages/`, `infrastructure/`, `docs/`).

**GitHub repository:** https://github.com/aidakablr3-lang/RestaurantOS — created and pushed to for the first time this session (§19). `origin` remote configured; all 3 local branches now have upstream tracking.

## 5. Git Branch

**Current branch:** `develop` (checked out to perform the merge; `feature/tenant-platform-frontend` still exists, untouched, not deleted per explicit instruction)

Branch structure (post-merge):

```
main                                 <- renamed from master; still at 1747258, not yet promoted
 └── develop                         <- MERGED: now contains all of feature/tenant-platform-frontend's history
      └── feature/tenant-platform-frontend   <- still exists (28 commits, HEAD 4294792), not deleted
```

**The merge is complete.** `develop` was merged with `feature/tenant-platform-frontend` via an explicit `--no-ff` merge commit (`80fcb9d`, two parents: old `develop` tip `1747258` and feature-branch tip `4294792`) — a real merge commit, not a fast-forward, not a squash, full history preserved. Pushed to `origin/develop`. `main` is unchanged, still at `1747258` — promoting `develop` into `main` is a separate, not-yet-requested action. See §20 for the full merge record.

## 6. Current HEAD Commit

```
80fcb9d3ba3d6fb0f00f928d6c223afc33e44e8e
```
(short: `80fcb9d` — `Merge feature/tenant-platform-frontend into develop`, on `develop`)

## 7. Working Tree Status

Clean (verified via `git status --porcelain` immediately before this document's own commit). After this document is committed, the tree returns to clean on `feature/tenant-platform-frontend`. Verify with `git status` (see §17).

## 8. Completed Work

### Sprint 0 — Product Blueprint
Full product PRD: personas, user stories, modules, screens, workflows, UX guidelines, business rules, roadmap. Document: `docs/architecture/product-blueprint.md`.

### Sprint 1 / 1.5 — Technical Architecture
v1.0 authored, independently reviewed (scored 5.8/10, NOT approved), remediated into **v2.0** (scored 9.5/10 on the core-platform scope, AI-readiness explicitly carved out as future work). Document: `docs/architecture/technical-architecture-v2.md`. Superseded v1.0 and its review are archived at `docs/architecture/superseded-technical-architecture-v1*.md`.

### Sprint 2 / 2.6 — Enterprise Data Architecture
v1.0 authored (60+ entity catalogue, multi-tenancy, offline sync, event architecture, performance, security, SQLAlchemy/Alembic patterns), independently reviewed (scored 7.2/10, 9 Critical + 8 High findings, NOT APPROVED), remediated into **v2.0** (all Critical/High findings closed; approved for implementation, core-platform scope). Document: `docs/architecture/data-architecture-v2.md`. Superseded v1.0 and its review are archived at `docs/architecture/superseded-data-architecture-v1*.md`.

### Sprint 3 — Identity Platform (backend)
Repo scaffolded to the Technical Architecture v2.0 monorepo layout; `modules/identity` built end-to-end for authentication: `Tenant`/`User`/`Session` domain entities, SQLAlchemy models + migration `0001`, Argon2id password hashing, RS256 JWT tokens, login/refresh/logout use cases + REST endpoints, full unit + integration test suite (44 tests), module README. **7 commits**, `f56869f` → `83690d0`.

### Sprint 4.1, Steps 1–2 — Tenant Platform (plan + backend)
Step 1 plan approved with 3 explicit architecture-compliance decisions (see §11). Step 2 backend implemented in **7 commits**, `1c6306c` → `1747258`:

1. `1c6306c` — Domain entities (`Subscription`, `SystemSetting`, `FeatureFlag`, `TenantDirectoryEntry`), `Tenant` lifecycle transitions, domain events, repository ports
2. `9616407` — Migration `0002` + SQLAlchemy models
3. `bcfa2ba` — Repository implementations + `OutboxWriter` (includes a disclosed mid-stream relocation fix — see §11)
4. `a215abb` — `VerifyAccessTokenUseCase` + auth/tenant-validation middleware (first protected routes in the codebase)
5. `e97c05b` — `TenantProvisioningService` + onboard/suspend/reactivate/offboard/update/get/list use cases
6. `529d9b3` — Subscription status, quota usage, settings, feature-flag use cases
7. `1747258` — REST API: admin router (platform-admin gated) + self-service router

Full PR-style writeup (files changed, technical decisions, testing evidence, rollback plan) was presented to the user and approved before Step 3 began.

### Sprint 4.1, Step 3 (partial) — Tenant Platform frontend

3 commits, `a76c5a9` → `fccea87`, on `feature/tenant-platform-frontend`:

1. `a76c5a9` — `chore(admin-web): scaffold Next.js admin-web app`. `create-next-app@15` (pinned — see §11) with App Router, `src/`, TypeScript, Tailwind v4; `shadcn@latest init` (pulled in **Base UI**, not Radix — shadcn's current default; components use a `render` prop for polymorphism, not `asChild`); shadcn primitives (button, card, input, label, table, badge, alert-dialog, form — form.tsx hand-written, see §11 — select, skeleton, textarea, tooltip); TanStack Query + next-themes providers, dark-mode toggle, sonner toasts. No business logic.
2. `1e0fc92` — `feat(admin-web): add authentication and API client`. `ApiResponse`/`ApiErrorResponse`-matching client types, a `fetch` wrapper (`apiClient`) that attaches the Bearer token and unwraps the envelope, a Zustand-persisted auth store, the login page (`POST /api/v1/auth/login`), and the `(admin)` route group's `AuthGuard` + app-shell layout (header, dark-mode toggle, logout).
3. `fccea87` — `feat(admin-web): tenant list, details, create, and edit flows`. Tenant List (paginated, status filter, loading/error/empty states), Tenant Details (with gated Suspend/Reactivate behind an `AlertDialog` confirmation), Create Tenant, Edit Tenant — all against `admin_tenant_router.py`'s endpoints.

Typecheck (`tsc --noEmit`), lint (`eslint`), and production build (`next build`) are all clean as of `fccea87`.

### Sprint 4.1, Step 3 continued — real-backend browser verification + 3 defect fixes

The Browser tool (blocked by a permission classifier at the end of the previous session) worked this session. To verify against a *real* backend rather than just the UI in isolation, a full local dev stack was stood up by hand (not committed — see §17): PostgreSQL 17 (installed via winget), migrations `0001`+`0002` applied, a generated RS256 dev keypair, `services/api` run directly via `uvicorn`, and two seed tenants/platform-admin users created via a throwaway script that reuses `TenantProvisioningService` (so provisioning invariants stay correct) plus a direct `UserModel` insert (no user-creation use case exists yet — expected, see Decision C).

3 commits, `07dea29` → `012bd8b`:

1. `07dea29` — `fix(database): use set_config() for transaction-local tenant context`. **Critical, found immediately on first real-Postgres write.** `UnitOfWork.__aenter__` issued `SET LOCAL app.tenant_id = :tenant_id` as a bound parameter; PostgreSQL's `SET`/`SET LOCAL` statement cannot take a bind parameter at all (confirmed with a minimal asyncpg-only repro, independent of this codebase) — every tenant-scoped transaction, in every module, would have failed the same way. Fixed to `SELECT set_config('app.tenant_id', :tenant_id, true)`, identical transaction-local semantics. User explicitly approved this as a "genuine production defect" before it was touched. Adds `tests/integration/platform/test_unit_of_work.py` (2 tests, requires `TEST_DATABASE_URL`) — verified by hand (git-stash the fix, confirm the tests reproduce the original error; restore the fix, confirm they pass) that they're a real regression test, since running them via `pytest` also surfaces a *separate*, pre-existing, out-of-scope bug: `tests/integration/conftest.py`'s `engine` fixture calls `asyncio.run()` from inside an already-running async fixture, which blocks the *entire* integration suite from executing in this environment. Not fixed (unrelated), disclosed here and in §11/§16.
2. `6e50f68` — `fix(api): add CORS middleware so browser clients can call the API`. **Second defect, found immediately after fixing #1: admin-web's login request never reached the backend at all.** The app had no `CORSMiddleware`; every browser's preflight `OPTIONS` request got `405 Method Not Allowed` with no `Access-Control-Allow-Origin` header, so the browser blocked the real request before it was ever sent. Added `Settings.cors_allowed_origins` (env `CORS_ALLOWED_ORIGINS`, defaults to admin-web's dev origin), `allow_credentials=False` (Bearer-token auth, never cookies, so nothing for credentialed CORS to protect). Adds `tests/unit/core/test_config.py` and `tests/unit/test_main.py` (TestClient preflight tests); required adding `httpx` as a dev dependency.
3. `012bd8b` — `fix(admin-web): defects found during real-backend browser verification`. Three frontend-only defects found by actually clicking through the app against real data: (a) tenant status values assumed uppercase (`"ACTIVE"`) but the backend's domain `TenantStatus` StrEnum serializes lowercase (`"active"`, plus `"provisioning"`/`"migrating"` the frontend type didn't even have) — this silently hid the Suspend/Reactivate buttons entirely, since neither status comparison ever matched; (b) the Edit Tenant form never pre-filled — `useForm`'s `values` option was given a fresh object literal every render and never took effect, replaced with the standard `defaultValues` + `useEffect` + `form.reset()` pattern; (c) every `Button` rendered as a `Link` logged a Base UI console warning (`nativeButton` defaults `true`, needs explicit `false` when rendering an `<a>` instead of a `<button>`).

All 7 flows (Login, Tenant List, Tenant Details, Create, Edit, Suspend, Reactivate) confirmed working post-fix via the Browser tool against the real stack; dark mode toggle confirmed; all four tenant pages confirmed free of console errors on a fresh load. No new functionality was added at any point in this pass — every change was a correction. User reviewed this and confirmed: "Step 3 is complete."

### Sprint 4.1, Step 4 — Testing

5 commits, `1962a45` → `695ea34`:

1. `1962a45` — `fix(services/api): restore the integration test suite`. Three compounding bugs fixed in `tests/integration/conftest.py`, none of which had let this suite actually execute end-to-end before this sprint: (a) the session-scoped `engine` fixture was async and called `_run_alembic_upgrade()`'s own `asyncio.run()` from inside an already-running pytest-asyncio loop — made the fixture a plain sync one, since `create_async_engine()` does no I/O at construction time; (b) fixing (a) exposed that importing `restaurant_os_api.main` (several test modules do, for a `TestClient`) runs `create_app()` at *module import* time, which calls the `@lru_cache`'d `get_settings()` before any fixture has set `DATABASE_URL` to the test database — permanently poisoning the cache with the production-default URL; fixed by setting `DATABASE_URL` at `conftest.py` *import* time instead of inside a fixture; (c) fixing (a) and (b) exposed that Starlette's `TestClient` (its own internal event loop) crashed reusing a connection opened by pytest-asyncio's loop — fixed with `poolclass=NullPool` on the test engine. Also found and fixed a **test-validity bug**, not just an infra one: the role that runs migrations owns every table it creates, and Postgres always lets a table owner bypass Row-Level Security (same as a superuser) — meaning `test_repositories.py`'s "single most important test" (RLS cross-tenant isolation) could have passed while testing nothing. `engine` now provisions and connects through a separate, unprivileged, non-owner role for actual test queries. Confirmed this mattered: without it, the RLS test's unfiltered query returned both tenants' rows and only failed because of its own assertion — it wasn't self-verifying. `pytest-asyncio`'s loop-scope config set to `"session"` in `pyproject.toml` to match the now-session-scoped engine. `_clean_tables`'s `TRUNCATE` list extended to cover every Sprint 4.1 table (it predated them). Full suite: 84/84 passing.
2. `215e355` — `test(services/api): add end-to-end integration tests for the Tenant Platform admin API`. 17 new tests, `test_admin_tenant_router.py`, following `test_auth_router.py`'s established real-HTTP-request-real-database pattern: onboard/list/get/update/suspend/reactivate/offboard, duplicate-legal-name conflict (409), invalid currency (422), pagination, status filtering, invalid status transitions (409), suspend-revokes-sessions, and the equivalent of the RLS suite's "most important test" pattern for this router — a non-platform-admin authenticated user rejected (403) from every admin endpoint. One existing backend design quirk asserted as current behavior, not fixed: `GET /admin/tenants/{unknown-id}` returns 401 (not 404) since `GetTenantUseCase` reuses the auth-time `TenantNotFoundError`.
3. `9af3ed4` — `chore(services/api): add reusable E2E fixture seed script`. `scripts/seed_e2e_fixtures.py` — idempotent, provisions a fixed platform-admin tenant/user for the new Playwright suite to log in as, against whatever database the backend under test is using.
4. `5cc5cfb` — `test(admin-web): add Playwright E2E suite for all 7 Tenant Administration flows`. 24 specs (`apps/admin-web/e2e/`) against a real running backend + database, exactly reproducing what Step 3's manual browser pass verified by hand. Every spec logs in through the real login form (Login is itself one of the covered flows). `global-setup.ts` fails fast with one clear message if the backend/fixture isn't reachable, instead of 24 confusing per-test failures. Found and fixed several **test-authoring** bugs while getting this green (documented in the commit, not application bugs): `TenantStatusBadge`'s CSS-only `capitalize` meant exact-case text assertions never matched the actual (lowercase) DOM text; Base UI's `Button` always exposes `role="button"` even rendered as a Link, so `getByRole("link", ...)` locators for Edit/Cancel never matched; Playwright's `getByRole`/`getByText` do case-insensitive *substring* matching by default, so `"Reactivate"` matched both the dialog trigger and its own "Reactivate tenant" confirm button (strict-mode violation) until `exact: true` was added.
5. `695ea34` — `fix(admin-web): don't clear the session for unrelated 401 responses`. **The one real application defect this pass found.** `apiClient.request()` cleared the session on *any* 401, but the backend also returns 401 for lookups unrelated to the caller's own session (`TENANT_NOT_FOUND` for an unknown admin-lookup ID, same enumeration-resistance reasoning as auth-time lookups, reused here where it doesn't really apply — the design quirk item 2 above disclosed and left alone). Visiting an unknown tenant ID was silently logging the platform admin all the way out to `/login` instead of showing the page's own error state. Now only clears the session for `INVALID_ACCESS_TOKEN`/`SESSION_REVOKED` — the codes that actually mean the token is dead. Verified via the Playwright suite: the "unknown tenant id shows an error state with retry" test now passes.

Full re-run after every fix: backend 84/84, Playwright 24/24 (confirmed twice, both fully green). `ruff format`/`ruff check`, `tsc --noEmit`, `eslint`, and `next build` all clean.

### Sprint 4.1, Step 5 — Release hardening

5 commits, `d9f5457` → `13b1bb2`:

1. `d9f5457` — `feat(infrastructure): add Docker Compose local dev environment`. Repo-root `docker-compose.yml` with `postgres` (postgres:17-alpine) and `api` services only — deliberately not the fuller nginx/redis/worker/beat/websocket/minio topology sketched in the superseded v1.0 architecture doc, since those services don't exist in the codebase yet; adding compose entries for processes that don't exist would just be inert scaffolding. `infrastructure/docker/api/Dockerfile` is a dev-hot-reload image (`python:3.13-slim`, `pip install -e ".[dev]"`, `uvicorn --reload`), explicitly not production-shaped (no multi-stage build, runs as root) — called out as a gap in the release checklist, not silently presented as prod-ready. `infrastructure/docker/dev-jwt/` holds a committed, clearly-labeled dev-only RS256 keypair (with its own README explaining why committing a *dev* keypair is safe: it signs nothing real, and CI generates its own throwaway pair per run instead of reusing it) — needed because Compose's `.env` file format can't carry a PEM's real newlines, so the `api` service reads the keys via `cat` from mounted files instead. **Not live-tested**: no Docker is installed in this environment, so `docker compose up` itself was never actually run; the compose file and Dockerfile were checked by hand against the manually-reproduced stack in §17 (same image, same env vars, same commands) instead. Disclosed in the commit message and in `docs/DEVELOPMENT.md`.
2. `db3dbe8` — `docs(repo): add local development guide`. `docs/DEVELOPMENT.md`: Option A (Docker Compose, the intended path, disclosed as not-live-tested) and Option B (the exact manual native-setup sequence this whole session actually used, since Docker wasn't available here — PostgreSQL via `initdb`, a dev JWT keypair, `uvicorn` directly), seeding, running every test suite (backend unit/integration, frontend typecheck/lint/build, Playwright E2E), and a troubleshooting section built from this session's own real errors (items 7–21 in the session's error log). `services/api/.env.example` added alongside it, documenting every environment variable the backend reads.
3. `5614d58` — `feat(services/api): add OpenAPI schema export`. `scripts/export_openapi.py` calls `app.openapi()` directly (no running server needed) and writes `docs/api/openapi.json` + a short `docs/api/README.md` explaining how/when to regenerate it. **Bug found and fixed during authoring, before it was ever committed wrong**: the script's `Path(__file__).resolve().parents[N]` initially used `parents[2]`, which resolved to `services/docs/openapi.json` instead of the repo-root `docs/api/openapi.json` — caught immediately (the file-write itself made the mistake visible), corrected to `parents[3]`, and the wrongly-created `services/docs/` directory was deleted before committing.
4. `75357a2` — `ci(repo): add GitHub Actions pipeline`. `.github/workflows/ci.yml`, 5 jobs: `backend-lint` (ruff), `backend-typecheck` (mypy, **advisory** — `continue-on-error: true`, see the mypy note below), `backend-test` (Postgres service container, full 84-test suite), `frontend` (tsc/eslint/build), `e2e` (Postgres service container + migrate + seed + start the API + Playwright, depends on `backend-test` and `frontend` passing first). Every job that needs a JWT keypair generates its own throwaway RS256 pair inline rather than reusing the committed dev-jwt one — a workflow run's logs are exactly the kind of place a leaked "dev" secret could get scraped from, so CI gets its own disposable pair every time. **Found in the process (not fixed, deliberately)**: running `mypy src/` surfaces 5 pre-existing type errors (`Argument 2 to "publish" of "OutboxWriter"` mismatches in 4 call sites + 1 stale `# type: ignore`) that predate this workflow and this sprint. Fixing them would be an application-code change outside Step 5's release-hardening scope (per the user's "no new business functionality" instruction), so the `backend-typecheck` job is deliberately non-blocking instead of silently skipped or silently ignored — the findings stay visible in CI output without gating merges on a pre-existing gap. **Not live-tested**: this repository has no git remote configured, so the workflow has never actually been run by GitHub's runners; it was authored against documented Actions syntax and this session's own equivalent local command sequence. Disclosed in the commit message and in `docs/RELEASE_CHECKLIST.md`.
5. `13b1bb2` — `docs(repo): update README and add a release checklist`. Root `README.md`'s "Getting Started" section replaced with real `docker compose up` + `npm run dev` instructions (previously placeholder text), Status section updated to reflect Steps 3–5, added Contributing and API Documentation sections linking to the new docs. `docs/RELEASE_CHECKLIST.md` (new): a pre-merge-to-`develop` checklist and a separate pre-promotion-to-`main` checklist, both derived from this sprint's own real incidents (e.g. explicitly calling out "don't skip the integration suite because unit tests are green — this sprint's own history is why," referencing the Step 4 conftest.py fix), plus an explicit "Not yet in place" section listing real gaps for an eventual production release (staging/prod deployment pipeline, a production-shaped Dockerfile, CI-enforced architecture-boundary linting, real secrets management, a CHANGELOG/version tags) that are deliberately out of scope for Sprint 4.1.

Full re-verification after all 5 commits: backend 84/84 passing, `ruff format --check`/`ruff check` clean, frontend `tsc --noEmit`/`eslint`/`next build` clean (confirmed in a fresh run right before this document was updated). Docker Compose and the GitHub Actions workflow itself remain the two pieces of Step 5 that could only be reviewed, not executed, in this environment (see §2's Step 5 paragraph and §11).

## 9. Current Work

Sprint 4.1 (Tenant Platform) is **merged into `develop`.** Steps 3, 4, and 5 are all done for their defined scope; Steps 3, 4, and 5 have all been explicitly signed off by the user ("Step 3 is complete", "Step 4 is complete", "The Tenant Platform Release Candidate (RC1) has passed review... Proceed with the merge"). The RC1 hardening pass, the GitHub push/CI verification pass, and the merge itself are all recorded in §18–§20. 4 admin-web screens remain explicitly deferred as future work per the user's decision (§2). No architecture files were touched at any point in this branch's life; the only backend runtime-code changes across Steps 3–5 and the RC1 pass (`07dea29`, `6e50f68`) were pre-approved critical-bug fixes — everything else was test/test-infrastructure, tooling, release-engineering, or documentation work, all now part of `develop`'s history.

## 10. Next Task

In priority order:

1. **Decide on `main`.** `develop` now has the Tenant Platform; `main` does not yet. Promoting `develop` → `main` is a separate, not-yet-requested action — `docs/RELEASE_CHECKLIST.md`'s "Before promoting `develop` into `main`" section requires full CI green *on `develop` itself* first (not just the feature branch), which hasn't been separately checked yet since the merge (see §20).
2. **The user has explicitly said to wait for approval before creating the first release tag** (e.g. `v0.1.0-rc1` as an actual git tag) — do not create one unprompted.
3. **`docker compose up --build` still needs a real run** on a machine with Docker installed — the one remaining unverified piece of this whole release (GitHub Actions is now confirmed, see §19).
4. **Decide what to do about the dev-JWT-keypair exposure in this branch's earlier commit history** (§11, §18) — the key itself is low-risk (never protected anything real), but a decision on whether to rewrite history belongs to whoever owns this repository, not something done unilaterally. Note this history is now part of `develop` too, post-merge.
5. **Resolve the Subscription/Quota/Feature-Flag/Settings gap** (§2, §11) if/when the user wants those 4 screens — needs the admin-scoped backend endpoints first, explicitly out of scope for this sprint per the user's instruction.
6. **The next sprint is an open decision, explicitly not to be started unprompted** ("Do NOT begin Restaurant Platform") — Sprint 4.1's own remaining scope (the 4 deferred screens) vs. starting the Restaurant Platform is the user's call.

## 11. Pending Tasks / Known Issues

**Pending (scheduled, not defects):**
- Sprint 4.1 Step 3 — Subscription Status, Quota Dashboard, Feature Flag Display, Tenant Settings screens: **deferred**, not built. Blocked on adding admin-scoped backend routes (e.g. `GET /api/v1/admin/tenants/{id}/subscription`) that reuse the existing self-service use cases with an admin-supplied `tenant_id` instead of the JWT-derived one. User explicitly confirmed: do not add these backend endpoints this sprint, treat as future work.
- **Do not merge `feature/tenant-platform-frontend` without an explicit go-ahead from the user in the same turn** — see §9/§10/§18. Everything is prepared; the merge itself hasn't run.
- **Docker Compose and GitHub Actions CI are authored and now more thoroughly checked than before, but still not live-tested** — no Docker in this environment (so `docker compose up --build` was never actually run) and no git remote configured (so `.github/workflows/ci.yml` has never actually executed on GitHub's runners). The RC1 pass (§18) found and fixed one real bug in each by *reproducing* the specific failure mode outside Docker/GitHub — stronger evidence than review alone, but still not the same as a real run. First priority for whoever has Docker + a GitHub remote.
- **The old committed dev JWT keypair (`infrastructure/docker/dev-jwt/{private,public}.pem`) still exists in this branch's earlier commit history** (§18) — removed from the working tree and future commits (`7ff7a6f`), not purged from history. Low practical risk (never protected anything real), but a deliberate decision for the repo owner if a full history rewrite is ever wanted.
- 5 pre-existing `mypy` findings (`OutboxWriter.publish` argument-type mismatches in 4 call sites + 1 stale `# type: ignore`) predate this sprint and are outside Step 5's release-hardening scope to fix (would be an application-code change). `backend-typecheck` in CI is deliberately non-blocking (`continue-on-error: true`) until someone decides to fix them.
- Sprint 4.1 backend business logic (tenant lifecycle, subscription, settings, feature flags) now has 17 new end-to-end integration tests (`test_admin_tenant_router.py`) covering the admin router's golden paths and key error/security cases, but this isn't exhaustive line-for-line coverage of every use case's every branch — e.g. offboard's own status-transition edge cases, settings/feature-flag self-service endpoints, and quota-usage calculations have no dedicated tests yet. A reasonable next increment if more backend test depth is wanted, not a gap that blocks anything today.

**Frontend implementation notes (disclosed, not bugs):**
- `create-next-app@latest` installs Next.js 16; the approved stack is Next.js 15, so `apps/admin-web` was scaffolded with `create-next-app@15` (currently resolves to `15.5.23`) instead. Pin this explicitly if re-scaffolding anything.
- `npm audit` reports 3 high-severity advisories (PostCSS XSS/path-traversal, sharp/libvips CVEs) as transitive dependencies of `next@15.5.23`'s own toolchain. The only fix `npm audit fix --force` offers is upgrading to `next@16`, which would violate the Next.js 15 pin above, so it was left as-is. Both are build/dev-tooling-time dependencies (CSS processing, image optimization), not something `admin-web`'s runtime code calls directly. Revisit when Next.js 15 ships a patch release, or explicitly re-decide the Next 15 vs 16 pin with the user.
- shadcn's current registry (`shadcn@4.16.2`, `style: base-nova`, Base UI) has no `form` component for this style — `shadcn add form` resolves but writes nothing (confirmed via `--dry-run`/`--view`: "No files"). `src/components/ui/form.tsx` was hand-written to match the classic shadcn form API (`Form`, `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormDescription`, `FormMessage`) using `React.cloneElement` instead of Radix's `Slot` (no Radix dependency was added, to stay consistent with the Base UI choice).
- Base UI components use a `render` prop for polymorphism (e.g. `<Button render={<Link href="..." />}>`), not Radix's `asChild` — every button-as-link/trigger in `apps/admin-web` uses `render`, not `asChild`. Base UI's `Button` also defaults `nativeButton={true}`; every such usage needs `nativeButton={false}` explicitly (see the 3rd defect fix above) since it renders an `<a>`, not a `<button>`.
- React Hook Form's `values` option (for syncing form state to async-loaded data) needs a *stable* object reference to work reliably — passing a freshly-constructed object literal inline on every render (as this session's first Edit Tenant implementation did) silently fails to populate the form. Use `defaultValues` + `useEffect` + `form.reset()` instead when the "default" data arrives asynchronously; that pattern is now what `apps/admin-web` uses (`tenants/[tenantId]/edit/page.tsx`).
- A platform-admin user that belongs to the same tenant it's administering will log itself out when it suspends that tenant (suspending a tenant revokes all of that tenant's sessions, correctly). Not a bug — just a reminder that a real deployment needs the platform-admin identity to live in a tenant distinct from any customer tenant it manages. This session's second seed tenant ("Platform Ops") exists specifically to avoid this when testing Suspend; `services/api/scripts/seed_e2e_fixtures.py` and the backend integration tests' `platform_admin_token` fixture both do the same thing for the same reason.
- `apiClient` only clears the auth session for `INVALID_ACCESS_TOKEN`/`SESSION_REVOKED` error codes now, not every 401 (see the Step 4 defect fix above) — if a future endpoint's 401 genuinely means "this session is dead" but uses a different error code, it needs adding to `TOKEN_INVALID_ERROR_CODES` in `src/lib/api-client.ts`.
- Playwright's `getByRole`/`getByText` do case-insensitive **substring** matching by default (not exact) — pass `exact: true` whenever one accessible name could be a substring of another nearby one (e.g. a "Reactivate" trigger button next to a "Reactivate tenant" confirm button), and scope text lookups to a specific container (e.g. `page.getByRole("alertdialog")`) when the same string legitimately appears more than once on a page (a tenant's display name appears in the heading, breadcrumb, detail fields, *and* an open confirmation dialog simultaneously).

**Architecture-compliance decisions made during Sprint 4.1 Step 1 (approved by user, no ADR required — these apply existing frozen architecture, they don't change it):**
- **Decision A:** Tenant Platform code extends `modules/identity` (Data Architecture v2.0 §12.5 already assigns `Tenant` there) rather than creating a new `modules/tenant`.
- **Decision B:** "Tenant soft delete" = the `OFFBOARDED` lifecycle status transition, not a new `deleted_at` column (Data Architecture v2.0 §5.2 explicitly has none).
- **Decision C:** Tenant-lifecycle mutation endpoints are gated by an interim `users.is_platform_admin` boolean — explicitly **not** RBAC. **Superseded as of Sprint 5 Step 2 (§21): full RBAC now exists** (`Role`/`Permission`/`RolePermission`/`UserRole`, migration `0003`, RBAC REST API). `is_platform_admin` itself is unchanged and structurally untouched by any RBAC code path (proven by test, §21) — it still gates platform-operator tenant administration; RBAC gates a tenant's own staff's access to future Restaurant Platform resources. The two mechanisms coexist by design, not by omission.

**Known scope boundaries (disclosed, not bugs):**
- The Transactional Outbox (`outbox_events`) durably and atomically records events, but the Redis Streams relay/dispatcher (Technical Architecture v2.0 Group D) is **not implemented** — no Redis client exists anywhere in the codebase yet.
- `VerifyAccessTokenUseCase`'s `permission_version` check is a direct PostgreSQL read, not the Redis-cached version Technical Architecture v2.0 Group C envisions at scale — correct, just not yet performance-optimized.
- `TenantDirectoryEntry` (Tenant Directory Service) exists as a data model only; there is no actual multi-shard connection routing (every tenant resolves to one connection today, per Data Architecture v2.0 §4.4's own stated scope).
- Mid-implementation correction during Commit 3: `OutboxEventModel` was initially placed inside `modules/identity` in Commit 2; relocated to `platform/outbox` (its correct, shared-kernel home) before anything else depended on the wrong location. Disclosed in the Commit 3 message, not silently fixed.

## 12. Architecture Version

**Technical Architecture v2.0** (`docs/architecture/technical-architecture-v2.md`) — approved for implementation (core-platform scope) following the Sprint 1.5 remediation. Frozen; do not modify without an ADR.

## 13. Data Architecture Version

**Enterprise Data Architecture v2.0** (`docs/architecture/data-architecture-v2.md`) — approved for implementation (core-platform / OLTP scope) following the Sprint 2.6 remediation. AI/analytics readiness is explicitly excluded from this approval and tracked as a separate future initiative. Frozen; do not modify without an ADR.

## 14. ADR Version

**No ADRs have been issued.** `docs/architecture/adr/` exists and is currently empty. Every decision point Sprint 4.1 encountered that touched the frozen architecture (see §11) was resolved via explicit user approval of an interpretation that stays *within* the existing documents, not via a formal architecture change — so no ADR was required per the "if an architectural change is required, STOP and create an ADR" rule. The first ADR, if one is ever needed, would be `docs/architecture/adr/0001-<title>.md`.

## 15. Current Migration Version

**`0002`** (`services/api/alembic/versions/0002_tenant_platform.py`), `down_revision = "0001"`. Both migrations are hand-written (not autogenerated) per Data Architecture v2.0 §7.1. No migration `0003` exists yet.

## 16. Test Status

- **Backend unit tests: 49/49 passing** (Sprint 3's original 44 + this sprint's 5 new CORS tests, `tests/unit/core/test_config.py` + `tests/unit/test_main.py`). No database required.
- **Backend integration tests: 18/18 passing** (`tests/integration/`, requires `TEST_DATABASE_URL`) — **the whole suite is executable for the first time this sprint**; see §8's Step 4 section for the three compounding bugs that blocked it before. `test_repositories.py` (10, Sprint 3, including the RLS cross-tenant isolation test — now provably meaningful, since it runs through an unprivileged, non-owner role, not the migration-owner role), `test_auth_router.py` (6, Sprint 3), `test_unit_of_work.py` (2, this sprint — the `set_config()` regression tests). **84 backend tests total, confirmed together in one run, twice.**
- **Backend admin-router integration tests: 17/17 passing** (`test_admin_tenant_router.py`, this sprint, requires `TEST_DATABASE_URL`) — real HTTP requests, real database, real auth middleware, covering onboard/list/get/update/suspend/reactivate/offboard plus security (403 for non-admin) and error cases. Included in the 84 total above.
- **Lint/compile (backend):** `ruff format`, `ruff check` all clean as of `695ea34`.
- **Frontend (`apps/admin-web`) typecheck/lint/build:** `npx tsc --noEmit`, `npx eslint .`, and `npm run build` all clean as of `695ea34`.
- **Frontend E2E: 24/24 passing** (`apps/admin-web/e2e/`, Playwright, this sprint) — a real browser (Chromium) against a real running `services/api` + PostgreSQL, covering all 7 flows Step 3 verified by hand: Login, Tenant List, Tenant Details, Create Tenant, Edit Tenant, Suspend Tenant, Reactivate Tenant. Confirmed on a from-scratch run (fresh dev server, fresh backend) — not a fluke of leftover state. See `apps/admin-web/e2e/README.md` for how to run it; requires `services/api/scripts/seed_e2e_fixtures.py` to have been run against the target database first.
- **CI pipeline:** `.github/workflows/ci.yml` (5 jobs — backend lint, backend typecheck (advisory), backend unit+integration tests against a Postgres service container, frontend typecheck/lint/build, Playwright E2E against a second Postgres service container) runs every test suite above automatically on push/PR to `main`/`develop`/`feature/**`. **Authored and reviewed, not yet live-executed** — this repository has no git remote configured in this environment, so GitHub's runners have never actually run it. First thing to confirm once a remote exists.
- **Local dev infrastructure:** `docker-compose.yml` + `infrastructure/docker/api/Dockerfile` bring up Postgres + the API with one command (§8 Step 5). **Authored and reviewed, not yet live-executed** — no Docker installed in this environment. The Docker-free manual sequence in §17 remains the confirmed-working path for now.

## 17. Commands to Resume Development

```bash
cd C:\Users\prash\Documents\RestaurantOS
git status
git log --oneline -5
git branch -vv
```

Additional useful commands for this specific handoff point:

```bash
# Confirm you're on the right branch
git branch --show-current
# Expect: feature/tenant-platform-frontend

# Confirm HEAD matches this document
git rev-parse HEAD
# Expect: 695ea348edb681e3be14b1f5f4a8bf8b070553f3

# Re-run the backend unit test suite (from services/api, no database needed)
cd services/api
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy python -m pytest tests/unit -q
# Expect: 49 passed

# Re-run the full backend suite including integration tests (needs a real
# Postgres -- see the "Reproducing this session's full local dev stack"
# section below, or point TEST_DATABASE_URL at your own instance)
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy TEST_DATABASE_URL="postgresql+asyncpg://<user>@<host>:<port>/<db>" python -m pytest tests/ -q
# Expect: 84 passed

# Frontend: install, configure, and run admin-web
cd apps/admin-web
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_BASE_URL at a running services/api
npm install
npx tsc --noEmit && npx eslint .   # Expect: both clean
npm run dev                        # Expect: ready on http://localhost:3000

# Frontend E2E (needs a running backend + admin-web dev server -- see
# apps/admin-web/e2e/README.md for the one-time fixture-seeding step)
npx playwright install chromium    # first time only
python services/api/scripts/seed_e2e_fixtures.py   # prints E2E_ADMIN_TENANT_ID
export E2E_ADMIN_TENANT_ID=<the tenantId it printed>
npm run e2e
# Expect: 24 passed
```

### Reproducing this session's full local dev stack (real Postgres + real API)

None of this is committed infrastructure yet (§11) — it's the manual sequence this session used to actually browser-verify against a real backend, kept here so the next session doesn't have to rediscover it:

```bash
# 1. PostgreSQL 17, if not already installed
winget install --id PostgreSQL.PostgreSQL.17 --silent --accept-package-agreements --accept-source-agreements

# 2. A standalone instance you own (sidesteps the installer service's
#    unknown/random superuser password entirely -- no admin rights needed)
initdb -D <some-data-dir> -U restaurantos --auth=trust -E UTF8
pg_ctl start -D <some-data-dir> -o "-p 5433 -c listen_addresses=localhost" -l <some-data-dir>/logfile
createdb -h localhost -p 5433 -U restaurantos restaurantos

# 3. RS256 dev keypair (JWT_PRIVATE_KEY=dummy only works for tests that
#    never actually sign/verify a real token)
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem

# 4. Python env + migrations (from services/api)
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
export JWT_PRIVATE_KEY="$(cat jwt_private.pem)" JWT_PUBLIC_KEY="$(cat jwt_public.pem)"
export DATABASE_URL="postgresql+asyncpg://restaurantos@localhost:5433/restaurantos"
./.venv/Scripts/python.exe -m alembic upgrade head

# 5. Seed a platform-admin tenant/user. For casual manual poking, use
#    services/api/scripts/seed_e2e_fixtures.py (committed, idempotent --
#    prints the tenantId to log in with). It provisions its own tenant,
#    so it never hits the self-suspend-logs-you-out gotcha (§11) as long
#    as you create/suspend a SEPARATE tenant through the UI to test with.

# 6. Run the API itself
export APP_ENV=development
export CORS_ALLOWED_ORIGINS="http://localhost:3000"   # or whatever port `npm run dev` picks
./.venv/Scripts/python.exe -m uvicorn restaurant_os_api.main:app --host 127.0.0.1 --port 8000

# 7. Point apps/admin-web/.env.local at it and `npm run dev`, then use the
#    Browser tool (or a real browser) against http://localhost:3000.
```

---

## 18. Release Candidate Status

**RC1 hardening pass, this session, user-directed via an explicit 8-step gate** ("prepare the Tenant Platform Release Candidate (RC1) for merge into develop... not a feature implementation sprint"). Full report: [`docs/releases/v0.1.0-rc1.md`](releases/v0.1.0-rc1.md).

**Steps completed:**

1. **Verified project state** — repo root, branch, HEAD, git status, and last 5 commits all confirmed to match what this document recorded at the time (one expected, disclosed self-referential lag in the HEAD commit hash — the same pattern this document has always had, since it can't cite its own commit).
2. **Removed the committed dev JWT private key** (`7ff7a6f`) — replaced with `infrastructure/docker/dev-jwt/generate-dev-keys.sh`/`.py`, updated `.gitignore`, `docker-compose.yml`, `docs/DEVELOPMENT.md`, `README.md`, `docs/RELEASE_CHECKLIST.md`. **Known limitation:** the removed key still exists in earlier commit history — not purged, since a history rewrite is a separate, more destructive decision than this pass was authorized to make unilaterally.
3. **GitHub preparation** — confirmed no remote is configured (`git remote -v` empty, no branch tracks an upstream). Reported, not invented; nothing pushed.
4. **GitHub Actions review** (`c1d4629`) — checked syntax, job dependencies, matrix usage, service containers, artifact paths, caching, and triggers. Found and fixed a real bug: `playwright.config.ts`'s default port (3100) didn't match the `e2e` job's hardcoded CORS allow-origin (3000) — every browser request in that job would have been CORS-rejected, failing all 24 E2E tests on first real run. Also fixed an artifact-upload step that had nothing to upload (CI-only reporter wrote no report file). Added pip caching and a concurrency group as routine hygiene.
5. **Docker review** (`b53ca56`) — Docker is not installed in this environment, so `docker compose up --build` was never run. Instead, statically reviewed `docker-compose.yml`/the Dockerfile (env-var wiring cross-checked against `core/config.py`'s actual `Settings` fields, YAML syntax validated, `.dockerignore` reviewed) and, critically, **reproduced the Dockerfile's exact `pip install -e .` sequence outside Docker** to test a suspected bug — confirmed it was real: copying only `pyproject.toml` before installing left the package permanently unimportable even after source was copied in later, which would have broken every `docker compose up --build` at the `alembic upgrade head` step (before uvicorn even started). Fixed by reordering the Dockerfile to copy source before installing.
6. **Fixed only verified issues** — all fixes above are CI/Docker/documentation only; no application code, no architecture changes, no new functionality.
7. **RC1 report** — [`docs/releases/v0.1.0-rc1.md`](releases/v0.1.0-rc1.md) (`5f6dacd`): executive summary, version, features, fixes, breaking changes (none), database changes, migration notes, a freshly re-run testing summary (84/84 backend, ruff/mypy/tsc/eslint/build all consistent with prior sessions), release metrics, known limitations, Docker status, GitHub Actions status, merge readiness, next sprint.
8. **This update.**

**Verification re-run fresh for this pass** (not carried over): backend unit 49/49, full suite (unit+integration) 84/84, `ruff format --check`/`ruff check` clean, `mypy src/` — same 5 pre-existing findings as before (unchanged), frontend `tsc --noEmit`/`eslint .`/`next build` all clean. Playwright's 24/24 was not re-run live this pass — the only Playwright-adjacent changes (`E2E_PORT` pin, CI-only `html` reporter) are both gated behind `process.env.CI`/`E2E_PORT`, neither set in a normal local run, so local behavior is provably unaffected; relying on this session's earlier-confirmed 24/24 with unchanged app/spec code.

**Remaining work as of the end of this pass (see §19 for what closed since):**
- ~~A real GitHub Actions run once this repository has a remote~~ — **done, see §19: repository pushed, CI confirmed passing.**
- A real `docker compose up --build` on a machine with Docker installed — still the one open item.
- A decision on whether the dev-JWT-keypair's presence in earlier commit history warrants a history rewrite (repo-owner decision, not made here).

**Merge recommendation (as of this pass): ready to merge into `develop`, pending explicit approval.** Superseded/reinforced by §19's update after the GitHub push and CI confirmation.

---

## 19. GitHub Push and CI Verification

**This session's scope, user-directed via an explicit 8-step gate**, immediately following the RC1 hardening pass above: the user created the GitHub repository (`https://github.com/aidakablr3-lang/RestaurantOS`, "intentionally empty") and directed this session to configure the remote, push all branches, verify CI, verify Docker (still unavailable), regenerate the RC1 report, update this document, and report — explicitly **not** to merge or push in a way that would authorize a merge.

**Steps completed:**

1. **Verified project state** — matched `docs/AI_HANDOFF.md` exactly (branch, HEAD `7bdc2db`, clean tree, last 5 commits).
2. **Configured `origin`** → `https://github.com/aidakablr3-lang/RestaurantOS.git`. Verified via `git remote -v`.
3. **Pushed all three required branches** (`main`, `develop`, `feature/tenant-platform-frontend`) with `git push -u origin main develop feature/tenant-platform-frontend` — all three set up to track their `origin` counterparts. Verified via `git branch -vv` (all three show `[origin/<branch>]`) and `git ls-remote origin` (all three refs present, hashes matching local exactly).
4. **Verified GitHub Actions** — `.github/workflows/ci.yml` only exists in `feature/tenant-platform-frontend`'s tree, so it triggered only on that branch's push (`main`'s and `develop`'s pushes triggered GitHub's own built-in dependency-graph submission workflow instead, unrelated to this repo). **Run [`31199349932`](https://github.com/aidakablr3-lang/RestaurantOS/actions/runs/31199349932), commit `7bdc2db`, conclusion: `success`.** All 5 jobs ran: `Frontend / typecheck, lint, build` ✅, `Backend / lint & format` ✅, `Backend / type check (advisory)` ⚠️ (expected — same 5 pre-existing `mypy` findings, non-blocking), `Backend / unit + integration tests` ✅ (full 84-test suite against a real Postgres service container), `End-to-end (Playwright)` ✅ (**directly confirms the prior pass's `E2E_PORT` CORS fix works on real infrastructure**, closing out the single biggest reasoning-not-observation gap from the previous RC1 pass). No failures — nothing to investigate or fix under this step.
5. **Verified Docker** — still not installed in this environment; stated plainly, not claimed. The successful CI run does **not** substitute for this: `ci.yml` never invokes `docker compose`, so `docker-compose.yml`/the Dockerfile remain exercised only by the previous pass's static review + outside-Docker reproduction, not a real `docker compose up --build`. This is now the **only** remaining unverified piece of this RC (GitHub Actions is no longer in that category).
6. **RC1 report updated** (`docs/releases/v0.1.0-rc1.md`, commit `09f4be8`) — Executive Summary, Version, Docker Status, and a new CI Status section with the full job breakdown; Release Metrics and Merge Readiness both updated to reflect the closed CI-verification gap.
7. **This update.**

**Remote configuration (verified this step):**
```
origin  https://github.com/aidakablr3-lang/RestaurantOS.git (fetch)
origin  https://github.com/aidakablr3-lang/RestaurantOS.git (push)
```
All three branches tracking: `main` → `origin/main`, `develop` → `origin/develop`, `feature/tenant-platform-frontend` → `origin/feature/tenant-platform-frontend`.

**CI status:** ✅ Passing (first-ever run on this repository). See run `31199349932` above.

**Docker status:** ⚪ Still unverified — not installed in this environment. Not claimed as working; the one clearly-flagged remaining gap.

**Merge readiness (updated):** **Ready to merge `feature/tenant-platform-frontend` → `develop`, pending explicit approval — stronger than the prior pass's recommendation**, since the GitHub Actions half of the "genuinely unverified" list from §18 has now closed with a real, green, first-ever run. Docker Compose remains the one open item, and it is infrastructure (fails loudly if wrong, doesn't silently corrupt `develop`), not application code. **No merge has been performed. Branches were pushed to `origin` this step, at the user's explicit instruction in this turn — that push is disclosed here as a completed fact, not treated as if it also authorized a merge.** Per the user's explicit instruction this turn ("Do NOT merge... Wait for my approval"), `git merge` will not run without a separate, explicit go-ahead.

---

## 20. Merge Completion

**The merge happened.** User approval, verbatim: *"Approved. The Tenant Platform Release Candidate (RC1) has passed review. GitHub verification is complete. GitHub Actions are green. Proceed with the merge."* — followed by an explicit 5-step gate for the merge itself.

**Steps completed:**

1. **Final verification before merging** — `git status` (clean), `git branch -vv` (all three branches tracking `origin`), `git log --oneline -5` (feature branch), plus an explicit ahead/behind check: `develop`/`origin/develop` and `feature/tenant-platform-frontend`/`origin/feature/tenant-platform-frontend` were each exactly `0 ahead, 0 behind` their remote counterpart before the merge — both branches fully pushed, nothing divergent.
2. **Merge** — checked out `develop`, ran `git merge --no-ff feature/tenant-platform-frontend` with a detailed merge-commit message summarizing the whole Tenant Platform release. Result: **merge commit `80fcb9d3ba3d6fb0f00f928d6c223afc33e44e8e`**, confirmed to have two parents (`1747258` = old `develop` tip, `4294792` = feature-branch tip) — a genuine merge commit. No fast-forward (explicitly avoided with `--no-ff`, since a fast-forward was otherwise available and would not have produced the "normal merge commit" the user asked for), no squash, no rebase. Full history preserved: all 43 commits from `feature/tenant-platform-frontend` are now reachable from `develop`. Merge was clean — no conflicts.
3. **Push** — `git push origin develop`: `1747258..80fcb9d develop -> develop`. Verified via `git branch -vv` (`develop` now tracks `origin/develop` at `80fcb9d`) and `git ls-remote origin` (`refs/heads/develop` = `80fcb9d3ba3d6fb0f00f928d6c223afc33e44e8e`, matching local exactly). `feature/tenant-platform-frontend` and `main` untouched, still present on both local and remote.
4. **This update.**

**Merge commit:** `80fcb9d3ba3d6fb0f00f928d6c223afc33e44e8e` (short `80fcb9d`)
**`develop` HEAD (post-merge, post-push):** `80fcb9d3ba3d6fb0f00f928d6c223afc33e44e8e`, confirmed identical on `origin/develop`
**RC1 status:** Merged. `v0.1.0-rc1`'s full content (93 files changed, 17,350 insertions, 17 deletions — the merge's own diffstat) is now part of `develop`'s history. No git tag has been created — the user explicitly said to wait for approval before creating the first release tag.
**Current repository status:** Working tree clean on `develop`. `feature/tenant-platform-frontend` still exists locally and remotely, not deleted (explicit instruction). `main` unchanged at `1747258`, not yet promoted.

**What did NOT happen, per explicit instruction:** the feature branch was not deleted; no git tag was created; the Restaurant Platform was not started; `main` was not touched.

---

## 21. Sprint 5 — Restaurant Platform Planning + RBAC Foundation

**Branch:** `feature/restaurant-platform`, created from `develop` at `f1acdf5`. **Not merged, not pushed** — per explicit instruction, awaiting separate approval. Working tree clean; HEAD is `7f7a2c6`.

**10 commits, in order:**

```
7f7a2c6 test(rbac): add authorization test matrix
47ee17e feat(identity): seed default RBAC roles during provisioning
9216e2e feat(rbac): add RBAC API
44d040c fix(rbac): prevent privilege escalation
e57145e feat(rbac): add authorization service
ae6cce5 feat(rbac): add permission resolution
46ef191 feat(rbac): add RBAC database migration
ce78d9c feat(rbac): add RBAC domain model
9b5c651 docs(architecture): add RBAC Foundation architecture (Sprint 5 Step 2 planning)
e9be036 docs(architecture): add Restaurant Platform architecture (Sprint 5 planning)
```

### Step 1 — Restaurant Platform architecture (documentation only)

`docs/architecture/RestaurantOS_Restaurant_Platform_Architecture.md` (861 lines, `e9be036`): bounded-context boundary, domain model, multi-tenancy, menu/table model, API/frontend boundaries, database design, offline-first, events, security/RBAC, test strategy, migration strategy, sprint breakdown, risks. **Critical finding from this pass:** the codebase had no RBAC at all — `is_platform_admin` is a single boolean that cannot express Restaurant Manager/Branch Manager/Waiter/Cashier/Kitchen Staff, each with different, sometimes branch-specific scope. User approved the architecture direction but explicitly blocked Restaurant Platform implementation on closing this gap first.

### Step 2 — RBAC Foundation (architecture + full implementation)

`docs/architecture/RBAC_Foundation_Architecture.md` (583 lines, `9b5c651`): RBAC domain model, role scope (platform/tenant/branch — one user can hold multiple simultaneous roles at different scopes), permission catalogue, authorization flow (JWT -> auth -> roles -> permissions -> tenant/branch scope, never embedding permissions in the JWT), `permission_version` interaction, Platform Admin coexistence, offline authorization design, audit/database/RLS/migration/API/testing strategy, security threats, risks, implementation sequence.

**Domain model implemented** (`ce78d9c`): `Role` (nullable `tenant_id` — NULL means platform-wide), `Permission` (code as TEXT primary key, mirroring `ChartOfAccount.account_code`), `RolePermission` (join), `UserRole` (`tenant_id` required, `branch_id` nullable — NULL = tenant-wide grant, set = branch-specific). `RoleGrantPolicy` (`domain/services/`, new package): a scope ceiling (actor's own `roles.assign` scope must cover the target) and a delegation ceiling (actor cannot hand out a permission they don't hold), composed into `ensure_can_grant`/`ensure_can_revoke`.

**Migration `0003`** (`46ef191`): `permissions`, `roles`, `role_permissions`, `user_roles`. `UNIQUE NULLS NOT DISTINCT` on `roles(tenant_id, name)` and `user_roles(user_id, role_id, branch_id)`. `roles`' RLS policy is deliberately widened (`tenant_id IS NULL OR tenant_id = current_setting(...)`, matching `feature_flags`' own precedent) so platform-wide roles stay visible from every tenant. Seeds exactly 11 permission codes (`restaurant.*`, `branch.*`, `table.*`, `menu.*`, `reservation.*`, `roles.assign`). `user_roles.branch_id` is a plain, unconstrained `TEXT` column — the FK to `branches.id` and a cross-table consistency trigger are explicitly deferred to migration `0004` (Restaurant Platform), documented in `0003`'s own docstring.

**Permission resolution + authorization** (`ae6cce5`, `e57145e`): `ResolveUserPermissionsUseCase` walks `UserRole` -> `Role` -> `RolePermission` -> `Permission`, aggregating into tenant-wide/by-branch sets — a fresh Postgres read on every call, never cached, never embedded in the JWT. `require_permission(code)`/`require_branch_permission(code)` FastAPI dependency factories gate routes; neither special-cases `is_platform_admin`.

**Privilege-escalation protection** (`44d040c`): `AssignUserRoleUseCase`/`RevokeUserRoleUseCase` check the granter/revoker's own freshly-resolved permissions against `RoleGrantPolicy` before writing anything. Every RBAC-affecting mutation bumps the *affected* user's `permission_version`.

**RBAC REST API** (`9216e2e`): `GET /api/v1/me/permissions` (auth only), `GET /api/v1/rbac/permissions`, `POST`/`GET /api/v1/rbac/roles`, `GET /api/v1/rbac/roles/{id}`, `PUT /api/v1/rbac/roles/{id}/permissions`, `POST /api/v1/rbac/user-roles`, `DELETE /api/v1/rbac/user-roles/{id}` — all mutating routes gated by `require_permission("roles.assign")` (tenant-wide only — see the finding below).

**Provisioning integration** (`47ee17e`): `TenantProvisioningService.provision()` now seeds the 7 default roles (Tenant Owner, Restaurant Manager, Branch Manager, Waiter, Cashier, Kitchen Staff, Bartender) + their permission grants for every *new* tenant, inside the same transaction as the rest of provisioning. Deliberately creates **no** `UserRole` grant (no user exists yet at provisioning time). `scripts/backfill_tenant_owner.py`: a standalone, manually-run script for tenants that predate this change — requires explicit `--tenant-id`/`--user-id` every time, never auto-discovers "the" owner, defaults to a dry-run preview, writes only with `--apply`.

**Comprehensive test matrix** (`7f7a2c6`): 76 new unit tests (domain, `ResolveUserPermissionsUseCase`, `AssignUserRoleUseCase`/`RevokeUserRoleUseCase`'s privilege-escalation matrix, `CreateRoleUseCase`/`ReplaceRolePermissionsUseCase`, the authorization dependencies) + 43 new integration tests against real PostgreSQL (every RBAC repository, RLS proven directly for both `roles`' widened predicate and `user_roles`' standard predicate, database constraints, and 19 full-stack HTTP tests through a real login flow).

### Two findings surfaced by the test matrix (real, disclosed, not fixed — decisions for the user)

1. **`permission_version` invalidation is strict-equality, not eventual-consistency.** Granting or revoking a role does not make the change visible to the *same*, already-issued access token on its next request — it immediately stales that token (401 `INVALID_ACCESS_TOKEN`, `verify_access_token.py:72`), forcing re-authentication. The RBAC architecture doc's framing ("no separate propagation mechanism needed") is true in the sense that the *next fresh token* always reflects the change with zero lag, but it does **not** mean an in-flight session silently sees new/removed access without re-logging in. Worth confirming this is the intended UX for `apps/admin-web` before Restaurant Platform frontend work assumes otherwise.
2. **Branch-scoped `roles.assign` cannot reach the RBAC API at all.** Every mutating RBAC route is gated by `require_permission("roles.assign")` (tenant-wide check only — it never consults a caller's branch-scoped grants). A user holding `roles.assign` only at one branch is rejected at the router layer (403 `PERMISSION_DENIED`) before ever reaching `AssignUserRoleUseCase`/`RevokeUserRoleUseCase`, whose `RoleGrantPolicy` scope ceiling *does* correctly support a branch-scoped granter (proven directly against the use cases in the unit tests). This is a real inconsistency between the domain layer's designed capability and the router's actual wiring — a legitimate Branch Manager cannot use the RBAC HTTP API for anything today, including managing their own branch's assignments. **Needs a decision:** either add a branch-aware variant of the `roles.assign` gate for `POST`/`DELETE /rbac/user-roles`, or explicitly decide branch-scoped `roles.assign` is out of scope for now and document that as intentional (today it is accidental, not decided).

### Verification evidence

Every commit was verified against a real, standalone PostgreSQL 17 instance (not just unit-level mocks) — migration upgrade/downgrade/upgrade, RLS proven via an unprivileged non-owner role, real FastAPI `TestClient` HTTP requests, real repository/UnitOfWork calls. Throwaway verification scripts were written to a scratch directory and deleted after each commit passed — never committed. Final state: **backend unit tests 125/125 passing** (49 pre-Sprint-5 + 76 new), **backend integration tests 78/78 passing** against real PostgreSQL (35 pre-Sprint-5 + 43 new), both suites run together with no cross-file interference. `ruff format`/`ruff check` clean across `src`, `tests`, `scripts`. `mypy` on `src`: 9 findings, all matching an already-disclosed `OutboxWriter.publish`/`DomainEvent` typing pattern (4 pre-existing + 5 new event-publish call sites added across Sprint 5) plus one pre-existing, unrelated `core/config.py` finding — no new class of problem. Migration `0003` upgrade/downgrade/upgrade cycle re-verified clean.

### Explicit stop point

Per the user's instruction: **do not proceed to Restaurant Platform Step 3 (business entities) without explicit approval.** Nothing in `modules/restaurant` or equivalent exists yet. This branch is not merged into `develop` and not pushed to GitHub.

---

## Engineering Status

**Completed Sprints:** 0 (Product Blueprint), 1 (Technical Architecture v1.0), 1.5 (TAD remediation → v2.0), 2 (Data Architecture v1.0), 2.6 (Data Architecture remediation → v2.0), 3 (Identity Platform backend), **4.1 (Tenant Platform, all 5 steps — merged into `develop`)**, **5 Steps 1–2 (Restaurant Platform architecture + RBAC Foundation — on `feature/restaurant-platform`, not yet merged; see §21)**.

**In progress:** Nothing actively in flight. Sprint 4.1 is merged into `develop` (merge commit `80fcb9d`, pushed to `origin/develop`) and unaffected by Sprint 5. Sprint 5's `feature/restaurant-platform` branch (10 commits, HEAD `7f7a2c6`, §21) is complete for its approved scope, not merged, not pushed, awaiting explicit approval before Restaurant Platform Step 3 (business entities) begins. Below this point (commit list, "Current Branch/PR/Milestone/Feature/Module") describes `develop`'s own state as of the Sprint 4.1 merge and is unchanged by Sprint 5 — see §21 for Sprint 5's own branch/commit/status details.

**Completed Commits on `develop` (44 total — 43 inherited from `feature/tenant-platform-frontend` plus the merge commit itself; `main` remains 30 commits behind, still at `1747258`; `feature/tenant-platform-frontend` still exists, untouched, at `4294792`):**

```
80fcb9d Merge feature/tenant-platform-frontend into develop
4294792 docs(repo): record GitHub push and CI verification in AI_HANDOFF.md
09f4be8 docs(releases): update v0.1.0-rc1 with real GitHub push and CI results
7bdc2db docs(repo): record RC1 hardening pass in AI_HANDOFF.md
5f6dacd docs(releases): add v0.1.0-rc1 release candidate report
a6aa9a0 docs(repo): note the Dockerfile build-order fix in DEVELOPMENT.md
b53ca56 fix(infrastructure): fix Dockerfile editable-install ordering that broke the build
c1d4629 ci(repo): fix CORS/port mismatch and unreachable Playwright report in E2E job
7ff7a6f security(repo): stop committing the dev JWT private key
b9c633a docs(repo): record Step 5 (release hardening) completion
13b1bb2 docs(repo): update README and add a release checklist
75357a2 ci(repo): add GitHub Actions pipeline
5614d58 feat(services/api): add OpenAPI schema export
db3dbe8 docs(repo): add local development guide
d9f5457 feat(infrastructure): add Docker Compose local dev environment
629b279 docs(repo): record Step 4 (testing) completion
695ea34 fix(admin-web): don't clear the session for unrelated 401 responses
5cc5cfb test(admin-web): add Playwright E2E suite for all 7 Tenant Administration flows
9af3ed4 chore(services/api): add reusable E2E fixture seed script
215e355 test(services/api): add end-to-end integration tests for the Tenant Platform admin API
1962a45 fix(services/api): restore the integration test suite
1b1174e docs(repo): record real-backend browser verification and 3 defect fixes
012bd8b fix(admin-web): defects found during real-backend browser verification
6e50f68 fix(api): add CORS middleware so browser clients can call the API
07dea29 fix(database): use set_config() for transaction-local tenant context
87ec07f docs(repo): update AI session handoff for Sprint 4.1 Step 3 progress
fccea87 feat(admin-web): tenant list, details, create, and edit flows
1e0fc92 feat(admin-web): add authentication and API client
a76c5a9 chore(admin-web): scaffold Next.js admin-web app
a1f83de docs(repo): add AI session handoff document
1747258 feat(identity): add Tenant Administration REST API
529d9b3 feat(identity): add subscription, settings, and feature-flag use cases
e97c05b feat(identity): add TenantProvisioningService and tenant lifecycle use cases
a215abb feat(auth): add authentication and tenant-validation middleware
bcfa2ba feat(identity): add repository implementations and the Outbox writer
9616407 feat(identity): add migration and models for the Tenant Platform schema
1c6306c feat(identity): add domain entities and events for the Tenant Platform
83690d0 docs(identity): add module README
3374e0c test(identity): add unit and integration tests for auth
4697a22 feat(auth): implement login, refresh, and logout with FastAPI routes
2799dde feat(identity): implement Argon2id password hashing and RS256 JWT tokens
d85bb6a feat(identity): add SQLAlchemy models and initial migration for identity schema
6a3da59 feat(identity): add domain layer for tenants, users, and sessions
f56869f chore(repo): scaffold monorepo structure and archive frozen architecture docs
```

**Current Branch:** `develop` (post-merge). `feature/tenant-platform-frontend` still exists, not deleted.

**Current PR:** None. The repository is on GitHub (`https://github.com/aidakablr3-lang/RestaurantOS`), but the merge was a direct local `git merge` + `git push origin develop`, not a pull request — no PR was ever opened for this work.

**Current Milestone:** Sprint 4.1 (Tenant Platform) — **merged into `develop`** via merge commit `80fcb9d`. RC1 hardening (removed a committed dev private key, fixed 2 real release-engineering bugs), a GitHub push + CI verification pass (confirmed both fixes on real infrastructure, first-ever green CI run), and the merge itself are all complete. Docker Compose remains the one still-not-live-tested piece (no Docker in this environment — see §11, §18, §19, §20). Full report: `docs/releases/v0.1.0-rc1.md`; full merge record: §20.

**Current Feature:** Tenant Platform (Sprint 4.1) — Tenant CRUD/lifecycle, Subscription, Settings, Feature Flags, Tenant Directory, Tenant Administration (backend complete, browser-verified, and integration-tested; frontend: List/Details/Create/Edit/Suspend/Reactivate built, browser-verified, and E2E-tested; Subscription/Quota/Feature-Flags/Settings explicitly deferred as future work per the user). Release-hardened and merged: Docker Compose, CI pipeline, developer docs, OpenAPI snapshot, release checklist all in place on `develop`.

**Current Module:** Backend — `services/api/src/restaurant_os_api/modules/identity` (extended, not new, per Decision A), plus its `tests/integration/` suite, `scripts/seed_e2e_fixtures.py`, and `scripts/export_openapi.py`. Frontend — `apps/admin-web` (Next.js 15 app), plus its `e2e/` Playwright suite. Infrastructure — `docker-compose.yml`, `infrastructure/docker/` (new this step). Docs — `docs/DEVELOPMENT.md`, `docs/RELEASE_CHECKLIST.md`, `docs/api/` (new this step).

---

*This document should be updated at the end of every session, or whenever a step/commit boundary is crossed, so the next session can resume without re-deriving context.*
