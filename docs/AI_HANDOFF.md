# RestaurantOS — AI Session Handoff Document

**Purpose:** This is the canonical handoff document for every future Claude session working on RestaurantOS. Read this file first, before touching any code, to reconstruct full project context.

**Last updated:** 2026-08-07
**Updated by:** Sprint 4.1 Step 3 session — admin-web scaffold, Tenant List/Details/Create/Edit/Suspend/Reactivate, real-backend browser verification, and 3 defect fixes found by it (1 backend, 1 CORS, 3 frontend)

---

## 1. Current Sprint

**Sprint 4.1 — Tenant Platform** (the first business platform; Product Blueprint Phase 1 / Technical Architecture v2.0 `modules/identity` extension).

## 2. Current Step

**Step 3 — Frontend implementation. Built, browser-verified end-to-end against a real backend, and fixed up. Not yet formally presented to the user for the Step 3 sign-off itself.** `apps/admin-web` is scaffolded and six of the ten originally-scoped screens are implemented, committed, and verified working in a real browser against a real running `services/api` + PostgreSQL: Tenant List, Tenant Details, Create Tenant, Edit Tenant, Suspend Tenant, Reactivate Tenant. **Scope was deliberately narrowed mid-session** — see the "Scope-down decision" note below and §11 — and the user approved that narrowing explicitly.

Sprint 4.1 follows a 5-step gated process, defined explicitly by the user:

| Step | Description | Status |
|---|---|---|
| 1 | Explain implementation plan, wait for approval | Complete — approved, including 3 explicit architecture-compliance decisions (see §11 Known Issues / Decisions) |
| 2 | Implement backend, wait for approval | Complete — 7 commits, approved |
| 3 | Implement frontend, wait for approval | **Implemented and verified; approval for the step itself has not been separately re-requested since verification finished.** 6/10 originally-scoped screens built and browser-verified (7 commits, `a76c5a9`→`012bd8b`) |
| 4 | Testing, wait for approval | Not started |
| 5 | Documentation, wait for approval | Not started |

**Scope-down decision (approved by the user):** The original Step 1 plan listed 10 admin-web screens, including Subscription Status, Quota Dashboard, Feature Flag Display, and Tenant Settings. Discovered mid-session: the backend only exposes those four as **self-service** endpoints (`/api/v1/tenants/me/*`), which resolve `tenant_id` from the caller's own JWT and structurally cannot take an admin-selected tenant ID (`self_service_tenant_router.py:1-4`, citing Data Architecture v2.0 §4.1 — tenant scope is never client-asserted). There is no admin-scoped route (e.g. `/api/v1/admin/tenants/{id}/subscription`) — the underlying use cases (`GetSubscriptionStatusUseCase`, `GetTenantQuotaUsageUseCase`, `GetTenantSettingsUseCase`, `ListFeatureFlagsUseCase`) already accept any `tenant_id` and could be wired to one, but that wiring doesn't exist yet. Presented to the user as a STOP with 3 options (add thin admin endpoints now / scope down / decide later); **user chose to scope down, and explicitly reconfirmed "do not add backend endpoints for Subscription, Quota, Feature Flags, or Tenant Settings in this sprint. Treat those as future work"** when giving the verification task. Those 4 screens are deferred, not abandoned — see §11.

**Real-backend browser verification (this session, user-requested as the direct follow-up to the scope-down decision):** Login, Tenant List, Tenant Details, Create Tenant, Edit Tenant, Suspend Tenant, and Reactivate Tenant were all exercised end-to-end in a real browser against a real `services/api` process backed by a real PostgreSQL 17 database (see §16, §17 for how this environment was stood up — it does not exist as committed infrastructure yet). This surfaced 3 real defects (1 backend, 1 backend CORS, 3 frontend — see §8's new subsection and §11), all fixed, each fix isolated to its own commit per the user's instruction. Not one line of new functionality was added during this pass — every change was a correction of something already in scope.

## 3. Current Milestone

Backend for the Tenant Platform is complete and merged to history (not yet to `main` via PR — see §9 Current PR). Frontend (`apps/admin-web`) is scaffolded (Next.js 15.5.23 App Router, React 19, TypeScript, Tailwind v4, shadcn/ui on Base UI primitives, TanStack Query, Zustand, React Hook Form + Zod) with Tenant List/Details/Create/Edit/Suspend/Reactivate implemented against the platform-admin REST API, and now **verified working end-to-end in a real browser against a real backend**. 4 of the original 10 screens remain deferred, explicitly confirmed as future work by the user (see §2, §11).

## 4. Repository Path

```
C:\Users\prash\Documents\RestaurantOS
```

This is both the Git repository root and the monorepo root (`services/api`, `apps/`, `packages/`, `infrastructure/`, `docs/`).

## 5. Git Branch

**Current branch:** `feature/tenant-platform-frontend`

Branch structure:

```
main                                 <- renamed from master
 └── develop                         <- created from main
      └── feature/tenant-platform-frontend   <- 7 commits ahead of develop/main (this session's admin-web work + fixes)
```

`main` and `develop` are still at `a1f83de` (the handoff-doc commit); only `feature/tenant-platform-frontend` has this session's new commits. Not yet merged up — Step 3's own sign-off hasn't been separately re-requested since verification finished.

## 6. Current HEAD Commit

```
012bd8baa2c96a623c962bcfa996797455331b23
```
(short: `012bd8b` — `fix(admin-web): defects found during real-backend browser verification`)

## 7. Working Tree Status

Clean immediately before this document's own commit (verified via `git status`). After this document is committed, the tree returns to clean on `feature/tenant-platform-frontend`. Verify with `git status` (see §17).

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

All 7 flows (Login, Tenant List, Tenant Details, Create, Edit, Suspend, Reactivate) confirmed working post-fix via the Browser tool against the real stack; dark mode toggle confirmed; all four tenant pages confirmed free of console errors on a fresh load. No new functionality was added at any point in this pass — every change was a correction.

## 9. Current Work

Sprint 4.1 Step 3 (Tenant Platform frontend) is implemented and browser-verified end-to-end against a real backend. 6 of the original 10 screens are built and verified; 4 remain explicitly deferred as future work per the user's decision (§2). No architecture files were touched this session; the two backend changes (`07dea29`, `6e50f68`) were both pre-approved, isolated, critical-bug fixes, not scope changes.

## 10. Next Task

In priority order:

1. **Get Step 3 formally signed off** — the 5-step gate calls for user approval at each step boundary; verification is done and defects are fixed, but a final "Step 3 approved, move to Step 4" checkpoint with the user hasn't happened as its own explicit exchange.
2. **Stand up committed local dev infrastructure.** This session's Postgres + backend + seed data were all manual, uncommitted, scratchpad-only setup (see §17) — reproducible by following §17's commands, but `infrastructure/docker`'s Docker Compose setup (flagged as pending since the Sprint 3 scaffold, per the repo README) still doesn't exist. Worth doing before Step 4 (testing) needs the same stack repeatedly.
3. **Resolve the Subscription/Quota/Feature-Flag/Settings gap** (§2, §11) if/when the user wants those 4 screens — needs the admin-scoped backend endpoints first, explicitly out of scope for this sprint per the user's latest instruction.
4. Once Step 3 is signed off, proceed to Step 4 (testing) and Step 5 (documentation) per the 5-step gate. Step 4 in particular should productionize this session's manual verification into the permanent pytest suite Sprint 4.1 still lacks (§11, §16) — the two new regression tests from this session's fixes are a start, not the whole job.

## 11. Pending Tasks / Known Issues

**Pending (scheduled, not defects):**
- Sprint 4.1 Step 3 — Subscription Status, Quota Dashboard, Feature Flag Display, Tenant Settings screens: **deferred**, not built. Blocked on adding admin-scoped backend routes (e.g. `GET /api/v1/admin/tenants/{id}/subscription`) that reuse the existing self-service use cases with an admin-supplied `tenant_id` instead of the JWT-derived one. User explicitly confirmed: do not add these backend endpoints this sprint, treat as future work.
- Sprint 4.1 Step 3 — a final "Step 3 signed off, move to Step 4" checkpoint with the user hasn't happened as its own exchange (see §10 item 1).
- Committed local dev infrastructure (Docker Compose for Postgres, etc.) still doesn't exist — flagged as pending since the Sprint 3 scaffold (repo README), still true. This session's entire verification stack (Postgres, keys, seed data) was manual and uncommitted (see §17) — reproducible, but not durable.
- Sprint 4.1 Step 4 — Formal automated test suite for the Tenant Platform backend (unit + integration + API + security tests as pytest cases). This session added 2 new integration tests (`tests/integration/platform/test_unit_of_work.py`) and 5 new unit tests (CORS), but the bulk of Sprint 4.1's own business logic (tenant lifecycle, subscription, settings, feature flags) still has no permanent pytest coverage — Sprint 3's 44 tests are unaffected and still pass. No automated tests exist for `apps/admin-web` either (no test runner is configured yet).
- Sprint 4.1 Step 5 — Documentation (identity module README needs a Tenant Platform section; `apps/admin-web/README.md` exists but is minimal)
- **A pre-existing, unrelated bug in `tests/integration/conftest.py`'s `engine` fixture** (session-scoped `pytest_asyncio.fixture` calling the synchronous `_run_alembic_upgrade()`, which itself calls `asyncio.run()` from inside an already-running event loop) blocks the *entire* integration test suite from executing in this environment — `RuntimeError: asyncio.run() cannot be called from a running event loop`. Found while verifying this session's new integration test; confirmed it's not specific to the new test by running the pre-existing `test_repositories.py` too (same failure). Out of scope for this session's fixes (unrelated to what was being fixed); needs its own fix before the integration suite can run at all, here or in CI.

**Frontend implementation notes (disclosed, not bugs):**
- `create-next-app@latest` installs Next.js 16; the approved stack is Next.js 15, so `apps/admin-web` was scaffolded with `create-next-app@15` (currently resolves to `15.5.23`) instead. Pin this explicitly if re-scaffolding anything.
- `npm audit` reports 3 high-severity advisories (PostCSS XSS/path-traversal, sharp/libvips CVEs) as transitive dependencies of `next@15.5.23`'s own toolchain. The only fix `npm audit fix --force` offers is upgrading to `next@16`, which would violate the Next.js 15 pin above, so it was left as-is. Both are build/dev-tooling-time dependencies (CSS processing, image optimization), not something `admin-web`'s runtime code calls directly. Revisit when Next.js 15 ships a patch release, or explicitly re-decide the Next 15 vs 16 pin with the user.
- shadcn's current registry (`shadcn@4.16.2`, `style: base-nova`, Base UI) has no `form` component for this style — `shadcn add form` resolves but writes nothing (confirmed via `--dry-run`/`--view`: "No files"). `src/components/ui/form.tsx` was hand-written to match the classic shadcn form API (`Form`, `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormDescription`, `FormMessage`) using `React.cloneElement` instead of Radix's `Slot` (no Radix dependency was added, to stay consistent with the Base UI choice).
- Base UI components use a `render` prop for polymorphism (e.g. `<Button render={<Link href="..." />}>`), not Radix's `asChild` — every button-as-link/trigger in `apps/admin-web` uses `render`, not `asChild`. Base UI's `Button` also defaults `nativeButton={true}`; every such usage needs `nativeButton={false}` explicitly (see the 3rd defect fix above) since it renders an `<a>`, not a `<button>`.
- React Hook Form's `values` option (for syncing form state to async-loaded data) needs a *stable* object reference to work reliably — passing a freshly-constructed object literal inline on every render (as this session's first Edit Tenant implementation did) silently fails to populate the form. Use `defaultValues` + `useEffect` + `form.reset()` instead when the "default" data arrives asynchronously; that pattern is now what `apps/admin-web` uses (`tenants/[tenantId]/edit/page.tsx`).
- A platform-admin user that belongs to the same tenant it's administering will log itself out when it suspends that tenant (suspending a tenant revokes all of that tenant's sessions, correctly). Not a bug — just a reminder that a real deployment needs the platform-admin identity to live in a tenant distinct from any customer tenant it manages. This session's second seed tenant ("Platform Ops") exists specifically to avoid this when testing Suspend.

**Architecture-compliance decisions made during Sprint 4.1 Step 1 (approved by user, no ADR required — these apply existing frozen architecture, they don't change it):**
- **Decision A:** Tenant Platform code extends `modules/identity` (Data Architecture v2.0 §12.5 already assigns `Tenant` there) rather than creating a new `modules/tenant`.
- **Decision B:** "Tenant soft delete" = the `OFFBOARDED` lifecycle status transition, not a new `deleted_at` column (Data Architecture v2.0 §5.2 explicitly has none).
- **Decision C:** Tenant-lifecycle mutation endpoints are gated by an interim `users.is_platform_admin` boolean — explicitly **not** RBAC. Full RBAC (`Role`/`Permission`/`RolePermission`/`UserRole`) remains deferred with no consumer yet.

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

- **Sprint 3 (Identity — auth):** 44/44 unit tests passing.
- **This session's new backend tests:** 5 new unit tests (CORS config parsing + preflight `TestClient` checks, `tests/unit/core/test_config.py` + `tests/unit/test_main.py`) — **49/49 unit tests passing total**. 2 new integration tests (`tests/integration/platform/test_unit_of_work.py`, requires `TEST_DATABASE_URL`) — verified correct by hand (not via `pytest`, which currently can't run this suite at all — see §11's disclosed `conftest.py` bug) by git-stashing the `set_config()` fix and confirming the tests fail with the exact original error, then restoring the fix and confirming they pass.
- **Sprint 4.1 backend business logic (tenant lifecycle, subscription, settings, feature flags):** Still no formal pytest suite (Step 4, pending). Verified during implementation via hands-on scripts against in-memory fakes and FastAPI's `TestClient`; evidence recorded in each commit's message. Additionally, this session ran the real thing — the actual `TenantProvisioningService`, `SuspendTenantUseCase`, `ReactivateTenantUseCase`, etc. — against a real PostgreSQL database via the running API and the Browser tool, for the first time (see §8).
- **Lint/compile (backend):** `ruff format`, `ruff check`, and `python -m py_compile` all clean as of `012bd8b`.
- **Sprint 4.1 frontend (`apps/admin-web`):** No test runner configured, no automated tests written. `npx tsc --noEmit`, `npx eslint .`, and `npm run build` (production build via Turbopack) are all clean as of `012bd8b`. **Browser-verified this session** — all 7 flows (Login, Tenant List, Tenant Details, Create, Edit, Suspend, Reactivate) confirmed working via the Browser tool against a real backend + real PostgreSQL; dark mode toggle confirmed; all 4 tenant pages confirmed free of console errors on a fresh load, after fixing 3 defects the verification found (§8, §11).

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
# Expect: 012bd8baa2c96a623c962bcfa996797455331b23

# Re-run the existing backend unit test suite (from services/api)
cd services/api
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy python -m pytest tests/unit -q
# Expect: 49 passed

# Frontend: install, configure, and run admin-web
cd apps/admin-web
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_BASE_URL at a running services/api
npm install
npx tsc --noEmit && npx eslint .   # Expect: both clean
npm run dev                        # Expect: ready on http://localhost:3000
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

# 5. Seed at least one tenant + platform-admin user -- there is no
#    user-creation use case/endpoint yet (Decision C), so this has to go
#    through TenantProvisioningService (for the tenant, to keep every
#    provisioning invariant correct) plus a direct UserModel insert (for
#    the user) inside a UnitOfWork(session_factory, TenantContext(tenant.id)).
#    Seed a SECOND tenant for the admin's own identity if you intend to
#    test Suspend on the first one -- suspending your own tenant logs you
#    out (§11, correct behavior, not a bug).

# 6. Run the API itself
export APP_ENV=development
export CORS_ALLOWED_ORIGINS="http://localhost:3000"   # or whatever port `npm run dev` picks
./.venv/Scripts/python.exe -m uvicorn restaurant_os_api.main:app --host 127.0.0.1 --port 8000

# 7. Point apps/admin-web/.env.local at it and `npm run dev`, then use the
#    Browser tool (or a real browser) against http://localhost:3000.
```

---

## Engineering Status

**Completed Sprints:** 0 (Product Blueprint), 1 (Technical Architecture v1.0), 1.5 (TAD remediation → v2.0), 2 (Data Architecture v1.0), 2.6 (Data Architecture remediation → v2.0), 3 (Identity Platform backend), 4.1 Steps 1–2 (Tenant Platform plan + backend).

**In progress:** Sprint 4.1 Step 3 (Tenant Platform frontend) — 6/10 screens, implemented and browser-verified end-to-end against a real backend; formal step sign-off with the user not yet separately re-requested (§10).

**Completed Commits (22 total on `feature/tenant-platform-frontend`; `main`/`develop` are 7 commits behind, still at `a1f83de`):**

```
012bd8b fix(admin-web): defects found during real-backend browser verification
6e50f68 fix(api): add CORS middleware so browser clients can call the API
07dea29 fix(database): use set_config() for transaction-local tenant context
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

**Current Branch:** `feature/tenant-platform-frontend`

**Current PR:** None. This repository has no remote configured — all work is local. No pull request has been opened (there is nothing to open one against yet).

**Current Milestone:** Sprint 4.1 Step 3 — Frontend implementation for the Tenant Platform. 6/10 screens built and browser-verified end-to-end against a real backend; formal step sign-off with the user not yet separately re-requested.

**Current Feature:** Tenant Platform (Sprint 4.1) — Tenant CRUD/lifecycle, Subscription, Settings, Feature Flags, Tenant Directory, Tenant Administration (backend complete and browser-verified; frontend: List/Details/Create/Edit/Suspend/Reactivate built and browser-verified, Subscription/Quota/Feature-Flags/Settings explicitly deferred as future work per the user).

**Current Module:** Backend — `services/api/src/restaurant_os_api/modules/identity` (extended, not new, per Decision A). Frontend — `apps/admin-web` (Next.js 15 app, scaffolded and partially built this session).

---

*This document should be updated at the end of every session, or whenever a step/commit boundary is crossed, so the next session can resume without re-deriving context.*
