# RestaurantOS — AI Session Handoff Document

**Purpose:** This is the canonical handoff document for every future Claude session working on RestaurantOS. Read this file first, before touching any code, to reconstruct full project context.

**Last updated:** 2026-08-07
**Updated by:** Sprint 4.1 Step 3 (frontend build + real-backend browser verification + defect fixes) and Step 4 (integration suite restored, 17 new backend integration tests, 24-spec Playwright E2E suite, 1 more real defect found and fixed)

---

## 1. Current Sprint

**Sprint 4.1 — Tenant Platform** (the first business platform; Product Blueprint Phase 1 / Technical Architecture v2.0 `modules/identity` extension).

## 2. Current Step

**Step 3 — Frontend implementation: built, browser-verified, fixed up, user-approved as complete.** **Step 4 — Testing: done for this sprint's scope.** `apps/admin-web` has six of the ten originally-scoped screens, verified working in a real browser against a real running `services/api` + PostgreSQL: Tenant List, Tenant Details, Create Tenant, Edit Tenant, Suspend Tenant, Reactivate Tenant. **Scope was deliberately narrowed mid-session** — see the "Scope-down decision" note below and §11 — user-approved. The manually-verified flows are now backed by automated tests: 17 new backend integration tests + a 24-spec Playwright E2E suite, both reproducible in CI once committed dev infrastructure exists (§11).

Sprint 4.1 follows a 5-step gated process, defined explicitly by the user:

| Step | Description | Status |
|---|---|---|
| 1 | Explain implementation plan, wait for approval | Complete — approved, including 3 explicit architecture-compliance decisions (see §11 Known Issues / Decisions) |
| 2 | Implement backend, wait for approval | Complete — 7 commits, approved |
| 3 | Implement frontend, wait for approval | **Complete — user explicitly confirmed "Step 3 is complete" after reviewing the real-backend browser verification results.** 6/10 originally-scoped screens (7 commits, `a76c5a9`→`012bd8b`) |
| 4 | Testing, wait for approval | **Done for this sprint's defined scope** (5 commits, `1962a45`→`695ea34`): integration test suite restored + extended, Playwright E2E suite added, both green. Not yet presented to the user for the Step 4 sign-off itself (see §10) |
| 5 | Documentation, wait for approval | Not started |

**Scope-down decision (approved by the user):** The original Step 1 plan listed 10 admin-web screens, including Subscription Status, Quota Dashboard, Feature Flag Display, and Tenant Settings. Discovered mid-session: the backend only exposes those four as **self-service** endpoints (`/api/v1/tenants/me/*`), which resolve `tenant_id` from the caller's own JWT and structurally cannot take an admin-selected tenant ID (`self_service_tenant_router.py:1-4`, citing Data Architecture v2.0 §4.1 — tenant scope is never client-asserted). There is no admin-scoped route (e.g. `/api/v1/admin/tenants/{id}/subscription`) — the underlying use cases (`GetSubscriptionStatusUseCase`, `GetTenantQuotaUsageUseCase`, `GetTenantSettingsUseCase`, `ListFeatureFlagsUseCase`) already accept any `tenant_id` and could be wired to one, but that wiring doesn't exist yet. Presented to the user as a STOP with 3 options (add thin admin endpoints now / scope down / decide later); **user chose to scope down, and explicitly reconfirmed "do not add backend endpoints for Subscription, Quota, Feature Flags, or Tenant Settings in this sprint. Treat those as future work"** when giving the Step 4 task. Those 4 screens are deferred, not abandoned — see §11.

**Real-backend browser verification (Step 3 close-out):** Login, Tenant List, Tenant Details, Create Tenant, Edit Tenant, Suspend Tenant, and Reactivate Tenant were all exercised end-to-end in a real browser against a real `services/api` process backed by a real PostgreSQL 17 database (see §16, §17 for how this environment was stood up — it does not exist as committed infrastructure yet). This surfaced 3 real defects (1 backend, 1 backend CORS, 3 frontend), all fixed, each isolated to its own commit. User reviewed and confirmed: **"Approved. Step 3 is complete... The production defects discovered during verification were valid, isolated, corrected, and committed separately."**

**Step 4 — Testing (this session, user-directed):** Scope given explicitly: fix the `conftest.py` fixture issue, restore the integration suite, add backend end-to-end integration tests, add frontend Playwright E2E tests for all 7 flows, target high coverage so the manually-verified flows become reproducible CI tests — **no new application functionality**. All delivered (§8). Along the way, writing and debugging the Playwright suite found **one more real application defect** (not a test bug): visiting an unknown tenant ID silently logged the platform admin all the way out, because the API client treated every 401 response as "this session is dead," when the backend also uses 401 for unrelated business-logic lookups. Fixed, isolated to its own commit, verified via the E2E suite. Not one line of new functionality was added — every change across all 5 Step 4 commits was a test, a test-infrastructure fix, or a correction of something already in scope.

## 3. Current Milestone

Backend for the Tenant Platform is complete, merged to history (not yet to `main` via PR — see §9), and now has 17 new end-to-end integration tests for the admin API, plus the pre-existing integration suite actually runs at all for the first time this sprint (2 more new tests there too). 24 new backend tests added this sprint (5 CORS unit + 2 `set_config()` integration + 17 admin-router integration); **84 backend tests total** across the whole codebase, all passing together. Frontend (`apps/admin-web`) is scaffolded (Next.js 15.5.23 App Router, React 19, TypeScript, Tailwind v4, shadcn/ui on Base UI primitives, TanStack Query, Zustand, React Hook Form + Zod) with Tenant List/Details/Create/Edit/Suspend/Reactivate implemented, browser-verified, and now covered by a 24-spec Playwright E2E suite (100% passing, confirmed twice). 4 of the original 10 screens remain deferred, explicitly confirmed as future work by the user (see §2, §11).

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
      └── feature/tenant-platform-frontend   <- 12 commits ahead of develop/main (Step 3 + Step 4 work)
```

`main` and `develop` are still at `a1f83de` (the handoff-doc commit); only `feature/tenant-platform-frontend` has all of Step 3's and Step 4's commits. Not yet merged up — user said "Do not merge yet" explicitly for both the Step 3 verification pass and the Step 4 testing pass.

## 6. Current HEAD Commit

```
695ea348edb681e3be14b1f5f4a8bf8b070553f3
```
(short: `695ea34` — `fix(admin-web): don't clear the session for unrelated 401 responses`)

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

All 7 flows (Login, Tenant List, Tenant Details, Create, Edit, Suspend, Reactivate) confirmed working post-fix via the Browser tool against the real stack; dark mode toggle confirmed; all four tenant pages confirmed free of console errors on a fresh load. No new functionality was added at any point in this pass — every change was a correction. User reviewed this and confirmed: "Step 3 is complete."

### Sprint 4.1, Step 4 — Testing

5 commits, `1962a45` → `695ea34`:

1. `1962a45` — `fix(services/api): restore the integration test suite`. Three compounding bugs fixed in `tests/integration/conftest.py`, none of which had let this suite actually execute end-to-end before this sprint: (a) the session-scoped `engine` fixture was async and called `_run_alembic_upgrade()`'s own `asyncio.run()` from inside an already-running pytest-asyncio loop — made the fixture a plain sync one, since `create_async_engine()` does no I/O at construction time; (b) fixing (a) exposed that importing `restaurant_os_api.main` (several test modules do, for a `TestClient`) runs `create_app()` at *module import* time, which calls the `@lru_cache`'d `get_settings()` before any fixture has set `DATABASE_URL` to the test database — permanently poisoning the cache with the production-default URL; fixed by setting `DATABASE_URL` at `conftest.py` *import* time instead of inside a fixture; (c) fixing (a) and (b) exposed that Starlette's `TestClient` (its own internal event loop) crashed reusing a connection opened by pytest-asyncio's loop — fixed with `poolclass=NullPool` on the test engine. Also found and fixed a **test-validity bug**, not just an infra one: the role that runs migrations owns every table it creates, and Postgres always lets a table owner bypass Row-Level Security (same as a superuser) — meaning `test_repositories.py`'s "single most important test" (RLS cross-tenant isolation) could have passed while testing nothing. `engine` now provisions and connects through a separate, unprivileged, non-owner role for actual test queries. Confirmed this mattered: without it, the RLS test's unfiltered query returned both tenants' rows and only failed because of its own assertion — it wasn't self-verifying. `pytest-asyncio`'s loop-scope config set to `"session"` in `pyproject.toml` to match the now-session-scoped engine. `_clean_tables`'s `TRUNCATE` list extended to cover every Sprint 4.1 table (it predated them). Full suite: 84/84 passing.
2. `215e355` — `test(services/api): add end-to-end integration tests for the Tenant Platform admin API`. 17 new tests, `test_admin_tenant_router.py`, following `test_auth_router.py`'s established real-HTTP-request-real-database pattern: onboard/list/get/update/suspend/reactivate/offboard, duplicate-legal-name conflict (409), invalid currency (422), pagination, status filtering, invalid status transitions (409), suspend-revokes-sessions, and the equivalent of the RLS suite's "most important test" pattern for this router — a non-platform-admin authenticated user rejected (403) from every admin endpoint. One existing backend design quirk asserted as current behavior, not fixed: `GET /admin/tenants/{unknown-id}` returns 401 (not 404) since `GetTenantUseCase` reuses the auth-time `TenantNotFoundError`.
3. `9af3ed4` — `chore(services/api): add reusable E2E fixture seed script`. `scripts/seed_e2e_fixtures.py` — idempotent, provisions a fixed platform-admin tenant/user for the new Playwright suite to log in as, against whatever database the backend under test is using.
4. `5cc5cfb` — `test(admin-web): add Playwright E2E suite for all 7 Tenant Administration flows`. 24 specs (`apps/admin-web/e2e/`) against a real running backend + database, exactly reproducing what Step 3's manual browser pass verified by hand. Every spec logs in through the real login form (Login is itself one of the covered flows). `global-setup.ts` fails fast with one clear message if the backend/fixture isn't reachable, instead of 24 confusing per-test failures. Found and fixed several **test-authoring** bugs while getting this green (documented in the commit, not application bugs): `TenantStatusBadge`'s CSS-only `capitalize` meant exact-case text assertions never matched the actual (lowercase) DOM text; Base UI's `Button` always exposes `role="button"` even rendered as a Link, so `getByRole("link", ...)` locators for Edit/Cancel never matched; Playwright's `getByRole`/`getByText` do case-insensitive *substring* matching by default, so `"Reactivate"` matched both the dialog trigger and its own "Reactivate tenant" confirm button (strict-mode violation) until `exact: true` was added.
5. `695ea34` — `fix(admin-web): don't clear the session for unrelated 401 responses`. **The one real application defect this pass found.** `apiClient.request()` cleared the session on *any* 401, but the backend also returns 401 for lookups unrelated to the caller's own session (`TENANT_NOT_FOUND` for an unknown admin-lookup ID, same enumeration-resistance reasoning as auth-time lookups, reused here where it doesn't really apply — the design quirk item 2 above disclosed and left alone). Visiting an unknown tenant ID was silently logging the platform admin all the way out to `/login` instead of showing the page's own error state. Now only clears the session for `INVALID_ACCESS_TOKEN`/`SESSION_REVOKED` — the codes that actually mean the token is dead. Verified via the Playwright suite: the "unknown tenant id shows an error state with retry" test now passes.

Full re-run after every fix: backend 84/84, Playwright 24/24 (confirmed twice, both fully green). `ruff format`/`ruff check`, `tsc --noEmit`, `eslint`, and `next build` all clean.

## 9. Current Work

Sprint 4.1 Steps 3 and 4 are both done for this sprint's defined scope. Step 3: 6/10 screens built, browser-verified, user-approved as complete. Step 4: integration suite restored (was never actually executable before this sprint), 17 new backend integration tests, a 24-spec Playwright E2E suite, one more real defect found and fixed by that work. 4 screens remain explicitly deferred as future work per the user's decision (§2). No architecture files were touched this session; every backend change (`07dea29`, `6e50f68`, `1962a45`, plus the new test files) was either a pre-approved critical-bug fix or pure test/test-infrastructure work — no scope changes, no new application functionality anywhere in Step 4.

## 10. Next Task

In priority order:

1. **Get Step 4 formally signed off** — testing is done for its given scope and everything is green, but a "Step 4 approved, move to Step 5" checkpoint with the user hasn't happened as its own exchange, mirroring how Step 3 needed its own explicit "Step 3 is complete" before this session moved on.
2. **Do not merge** `feature/tenant-platform-frontend` — the user has said this explicitly twice now (once after Step 3 verification, again when assigning Step 4). Wait for explicit instruction before merging to `develop`/`main`.
3. **Stand up committed local dev infrastructure.** Every test in this sprint (integration + Playwright) still depends on a manually-provisioned Postgres + backend that isn't committed anywhere (see §17) — reproducible by following §17's commands, but `infrastructure/docker`'s Docker Compose setup (flagged as pending since the Sprint 3 scaffold, per the repo README) still doesn't exist. This is what would let CI actually run these new test suites; right now they're real and passing, but only runnable by hand.
4. **Resolve the Subscription/Quota/Feature-Flag/Settings gap** (§2, §11) if/when the user wants those 4 screens — needs the admin-scoped backend endpoints first, explicitly out of scope for this sprint per the user's instruction.
5. Once Step 4 is signed off, proceed to Step 5 (documentation) per the 5-step gate — identity module README needs a Tenant Platform section, `apps/admin-web/README.md` needs an update to mention the new `e2e/` suite.

## 11. Pending Tasks / Known Issues

**Pending (scheduled, not defects):**
- Sprint 4.1 Step 3 — Subscription Status, Quota Dashboard, Feature Flag Display, Tenant Settings screens: **deferred**, not built. Blocked on adding admin-scoped backend routes (e.g. `GET /api/v1/admin/tenants/{id}/subscription`) that reuse the existing self-service use cases with an admin-supplied `tenant_id` instead of the JWT-derived one. User explicitly confirmed: do not add these backend endpoints this sprint, treat as future work.
- Sprint 4.1 Step 4 — a final "Step 4 signed off, move to Step 5" checkpoint with the user hasn't happened as its own exchange (see §10 item 1). Do not merge `feature/tenant-platform-frontend` until told to.
- Committed local dev infrastructure (Docker Compose for Postgres, etc.) still doesn't exist — flagged as pending since the Sprint 3 scaffold (repo README), still true, and now blocks more than before: both the integration suite and the Playwright suite are real and passing, but only runnable by hand against a manually-provisioned stack (see §17), not in CI. This is the natural next piece of infrastructure work.
- Sprint 4.1 Step 5 — Documentation (identity module README needs a Tenant Platform section; `apps/admin-web/README.md` doesn't mention the new `e2e/` suite yet)
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

- **Backend unit tests: 49/49 passing** (Sprint 3's original 44 + this sprint's 5 new CORS tests, `tests/unit/core/test_config.py` + `tests/unit/test_main.py`). No database required.
- **Backend integration tests: 18/18 passing** (`tests/integration/`, requires `TEST_DATABASE_URL`) — **the whole suite is executable for the first time this sprint**; see §8's Step 4 section for the three compounding bugs that blocked it before. `test_repositories.py` (10, Sprint 3, including the RLS cross-tenant isolation test — now provably meaningful, since it runs through an unprivileged, non-owner role, not the migration-owner role), `test_auth_router.py` (6, Sprint 3), `test_unit_of_work.py` (2, this sprint — the `set_config()` regression tests). **84 backend tests total, confirmed together in one run, twice.**
- **Backend admin-router integration tests: 17/17 passing** (`test_admin_tenant_router.py`, this sprint, requires `TEST_DATABASE_URL`) — real HTTP requests, real database, real auth middleware, covering onboard/list/get/update/suspend/reactivate/offboard plus security (403 for non-admin) and error cases. Included in the 84 total above.
- **Lint/compile (backend):** `ruff format`, `ruff check` all clean as of `695ea34`.
- **Frontend (`apps/admin-web`) typecheck/lint/build:** `npx tsc --noEmit`, `npx eslint .`, and `npm run build` all clean as of `695ea34`.
- **Frontend E2E: 24/24 passing** (`apps/admin-web/e2e/`, Playwright, this sprint) — a real browser (Chromium) against a real running `services/api` + PostgreSQL, covering all 7 flows Step 3 verified by hand: Login, Tenant List, Tenant Details, Create Tenant, Edit Tenant, Suspend Tenant, Reactivate Tenant. Confirmed on a from-scratch run (fresh dev server, fresh backend) — not a fluke of leftover state. See `apps/admin-web/e2e/README.md` for how to run it; requires `services/api/scripts/seed_e2e_fixtures.py` to have been run against the target database first.
- **What's still manual, not yet in CI:** every test above requires a real PostgreSQL instance and, for the Playwright suite, a real running backend + frontend dev server — none of which is committed infrastructure yet (§11, §17). The tests themselves are real and reproducible; the environment they need isn't automated yet.

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

## Engineering Status

**Completed Sprints:** 0 (Product Blueprint), 1 (Technical Architecture v1.0), 1.5 (TAD remediation → v2.0), 2 (Data Architecture v1.0), 2.6 (Data Architecture remediation → v2.0), 3 (Identity Platform backend), 4.1 Steps 1–2 (Tenant Platform plan + backend).

**In progress:** Sprint 4.1 Step 4 (Testing) — done for its given scope, all green; formal step sign-off with the user not yet separately re-requested (§10). Step 3 is complete and user-approved.

**Completed Commits (27 total on `feature/tenant-platform-frontend`; `main`/`develop` are 12 commits behind, still at `a1f83de`):**

```
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

**Current Branch:** `feature/tenant-platform-frontend`

**Current PR:** None. This repository has no remote configured — all work is local. No pull request has been opened (there is nothing to open one against yet).

**Current Milestone:** Sprint 4.1 Step 4 — Testing for the Tenant Platform. Done for its given scope (integration suite restored + extended, Playwright E2E suite added, 108 tests total across both, all green); formal step sign-off with the user not yet separately re-requested.

**Current Feature:** Tenant Platform (Sprint 4.1) — Tenant CRUD/lifecycle, Subscription, Settings, Feature Flags, Tenant Directory, Tenant Administration (backend complete, browser-verified, and integration-tested; frontend: List/Details/Create/Edit/Suspend/Reactivate built, browser-verified, and E2E-tested; Subscription/Quota/Feature-Flags/Settings explicitly deferred as future work per the user).

**Current Module:** Backend — `services/api/src/restaurant_os_api/modules/identity` (extended, not new, per Decision A), plus its `tests/integration/` suite (restored and extended this sprint) and `scripts/seed_e2e_fixtures.py`. Frontend — `apps/admin-web` (Next.js 15 app), plus its new `e2e/` Playwright suite.

---

*This document should be updated at the end of every session, or whenever a step/commit boundary is crossed, so the next session can resume without re-deriving context.*
