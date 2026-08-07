# RestaurantOS — AI Session Handoff Document

**Purpose:** This is the canonical handoff document for every future Claude session working on RestaurantOS. Read this file first, before touching any code, to reconstruct full project context.

**Last updated:** 2026-08-07
**Updated by:** Sprint 4.1 Step 3 session — admin-web scaffold + Tenant List/Details/Create/Edit/Suspend/Reactivate

---

## 1. Current Sprint

**Sprint 4.1 — Tenant Platform** (the first business platform; Product Blueprint Phase 1 / Technical Architecture v2.0 `modules/identity` extension).

## 2. Current Step

**Step 3 — Frontend implementation. In progress, not yet complete, not yet presented for approval.** `apps/admin-web` is scaffolded and six of the ten originally-scoped screens are implemented and committed: Tenant List, Tenant Details, Create Tenant, Edit Tenant, Suspend Tenant, Reactivate Tenant (all with loading/error/empty states, responsive layout, dark mode, and accessible shadcn/Base UI primitives). **Scope was deliberately narrowed mid-session** — see the "Scope-down decision" note below and §11.

Sprint 4.1 follows a 5-step gated process, defined explicitly by the user:

| Step | Description | Status |
|---|---|---|
| 1 | Explain implementation plan, wait for approval | Complete — approved, including 3 explicit architecture-compliance decisions (see §11 Known Issues / Decisions) |
| 2 | Implement backend, wait for approval | Complete — 7 commits, approved |
| 3 | Implement frontend, wait for approval | **In progress** — 6/10 originally-scoped screens built (3 commits, `a76c5a9`→`fccea87`); not yet presented to the user for approval; not yet browser-verified (see §16) |
| 4 | Testing, wait for approval | Not started |
| 5 | Documentation, wait for approval | Not started |

**Scope-down decision (this session, approved by the user):** The original Step 1 plan listed 10 admin-web screens, including Subscription Status, Quota Dashboard, Feature Flag Display, and Tenant Settings. Discovered mid-session: the backend only exposes those four as **self-service** endpoints (`/api/v1/tenants/me/*`), which resolve `tenant_id` from the caller's own JWT and structurally cannot take an admin-selected tenant ID (`self_service_tenant_router.py:1-4`, citing Data Architecture v2.0 §4.1 — tenant scope is never client-asserted). There is no admin-scoped route (e.g. `/api/v1/admin/tenants/{id}/subscription`) — the underlying use cases (`GetSubscriptionStatusUseCase`, `GetTenantQuotaUsageUseCase`, `GetTenantSettingsUseCase`, `ListFeatureFlagsUseCase`) already accept any `tenant_id` and could be wired to one, but that wiring doesn't exist yet. Presented to the user as a STOP with 3 options (add thin admin endpoints now / scope down / decide later); **user chose to scope down**. Those 4 screens are deferred, not abandoned — see §11.

## 3. Current Milestone

Backend for the Tenant Platform is complete and merged to history (not yet to `main` via PR — see §9 Current PR). Frontend (`apps/admin-web`) is scaffolded (Next.js 15.5.23 App Router, React 19, TypeScript, Tailwind v4, shadcn/ui on Base UI primitives, TanStack Query, Zustand, React Hook Form + Zod) with Tenant List/Details/Create/Edit/Suspend/Reactivate implemented against the platform-admin REST API. Not yet browser-verified in this session (tooling permission denial — see §16), not yet reviewed/approved by the user, and 4 of the original 10 screens are deferred pending a backend decision (see §2, §11).

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
      └── feature/tenant-platform-frontend   <- 3 commits ahead of develop/main (this session's admin-web work)
```

`main` and `develop` are still at `a1f83de` (the handoff-doc commit); only `feature/tenant-platform-frontend` has this session's 3 new commits. Not yet merged up — Step 3 isn't finished or approved yet.

## 6. Current HEAD Commit

```
fccea87460f1ec0e2df0ede5f5121629970a01b0
```
(short: `fccea87` — `feat(admin-web): tenant list, details, create, and edit flows`)

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

Typecheck (`tsc --noEmit`), lint (`eslint`), and production build (`next build`) are all clean as of `fccea87`. **Not yet browser-verified** (see §11, §16) and **not yet presented to the user for Step 3 approval** — this handoff point is mid-step, not a step boundary.

## 9. Current Work

Sprint 4.1 Step 3 (Tenant Platform frontend), scoped down mid-session — see §2's "Scope-down decision". 6 of the original 10 screens are built; 4 are deferred pending a backend decision. No backend or architecture files were touched this session.

## 10. Next Task

In priority order:

1. **Get this session's frontend work reviewed and approved by the user** (per Step 3's own gate) before treating it as done — it has not been presented for approval yet.
2. **Browser-verify the app for real.** This session could not open the Browser pane (`preview_start` was denied twice by the harness's permission classifier — see §11). The dev server itself boots cleanly (`npm run dev` in `apps/admin-web`, confirmed via server log, port 3001 in this session), but no screen has been visually confirmed to render or interact correctly, and the login flow has never been exercised against a live backend (no `services/api` instance or Postgres was running this session either). Do this before claiming the 6 built screens work.
3. **Resolve the Subscription/Quota/Feature-Flag/Settings gap** (§2, §11) — get a decision on adding the 4 admin-scoped backend endpoints, then build those screens if approved.
4. Once the above are done and Step 3 is user-approved, proceed to Step 4 (testing) and Step 5 (documentation) per the 5-step gate.

## 11. Pending Tasks / Known Issues

**Pending (scheduled, not defects):**
- Sprint 4.1 Step 3 — Frontend: 6/10 screens built, not yet browser-verified, not yet user-approved (see §2, §9, §10)
- Sprint 4.1 Step 3 — Subscription Status, Quota Dashboard, Feature Flag Display, Tenant Settings screens: **deferred**, not built. Blocked on adding admin-scoped backend routes (e.g. `GET /api/v1/admin/tenants/{id}/subscription`) that reuse the existing self-service use cases with an admin-supplied `tenant_id` instead of the JWT-derived one. User was given 3 options (add the endpoints now / scope down / decide later) and chose to scope down for this session — the decision to add those endpoints is still open, not rejected.
- Sprint 4.1 Step 3 — Browser verification never happened this session. `preview_start` was denied twice by the harness's own permission classifier (not a user denial, not a code issue) — see §10 item 2. The dev server itself starts cleanly; nothing beyond that was confirmed.
- Sprint 4.1 Step 4 — Formal automated test suite for the Tenant Platform backend (unit + integration + API + security tests as pytest cases; the backend was verified via hands-on scripted checks during implementation, documented in each commit message, but no permanent pytest files exist yet for Sprint 4.1 — Sprint 3's 44 tests are unaffected and still pass). No automated tests exist for `apps/admin-web` either (no test runner is configured yet).
- Sprint 4.1 Step 5 — Documentation (identity module README needs a Tenant Platform section; `apps/admin-web/README.md` exists but is minimal)

**Frontend implementation notes (disclosed, not bugs):**
- `create-next-app@latest` installs Next.js 16; the approved stack is Next.js 15, so `apps/admin-web` was scaffolded with `create-next-app@15` (currently resolves to `15.5.23`) instead. Pin this explicitly if re-scaffolding anything.
- `npm audit` reports 3 high-severity advisories (PostCSS XSS/path-traversal, sharp/libvips CVEs) as transitive dependencies of `next@15.5.23`'s own toolchain. The only fix `npm audit fix --force` offers is upgrading to `next@16`, which would violate the Next.js 15 pin above, so it was left as-is. Both are build/dev-tooling-time dependencies (CSS processing, image optimization), not something `admin-web`'s runtime code calls directly. Revisit when Next.js 15 ships a patch release, or explicitly re-decide the Next 15 vs 16 pin with the user.
- shadcn's current registry (`shadcn@4.16.2`, `style: base-nova`, Base UI) has no `form` component for this style — `shadcn add form` resolves but writes nothing (confirmed via `--dry-run`/`--view`: "No files"). `src/components/ui/form.tsx` was hand-written to match the classic shadcn form API (`Form`, `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormDescription`, `FormMessage`) using `React.cloneElement` instead of Radix's `Slot` (no Radix dependency was added, to stay consistent with the Base UI choice).
- Base UI components use a `render` prop for polymorphism (e.g. `<Button render={<Link href="..." />}>`), not Radix's `asChild` — every button-as-link/trigger in `apps/admin-web` uses `render`, not `asChild`.

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

- **Sprint 3 (Identity — auth):** 44/44 unit tests passing. Integration tests exist (`tests/integration/`) but require a live PostgreSQL instance to execute; not run in this environment.
- **Sprint 4.1 backend (Tenant Platform):** No formal pytest suite yet (Step 4, pending). Verified during implementation via hands-on scripts against in-memory fakes and FastAPI's `TestClient` — full lifecycle, security (403 on non-admin), subscription/quota/settings/feature-flag logic, and validation paths all confirmed working; evidence recorded in each commit's message. These scripts were run from the scratchpad directory and are **not** part of the committed test suite.
- **Lint/compile (backend):** `ruff format`, `ruff check`, and `python -m py_compile` all clean as of `1747258`.
- **Sprint 4.1 frontend (`apps/admin-web`):** No test runner configured, no automated tests written. `npx tsc --noEmit`, `npx eslint .`, and `npm run build` (production build via Turbopack) are all clean as of `fccea87`. **No browser verification happened** — `preview_start` was denied twice by the harness's permission classifier this session (not attributable to the code); the dev server was confirmed to boot (`npm run dev`, "Ready in 8.3s" on port 3001) but no page was ever actually loaded, rendered, or interacted with. Login was never exercised against a live `services/api` — no backend or Postgres instance was running this session. Treat every screen as **unverified** until someone opens it in a browser against a running backend.

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
# Expect: fccea87460f1ec0e2df0ede5f5121629970a01b0

# Re-run the existing backend test suite (from services/api)
cd services/api
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy python -m pytest tests/unit -q
# Expect: 44 passed

# Inspect the current migration state (dry-run, no DB required)
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db" python -m alembic upgrade head --sql

# Frontend: install, configure, and run admin-web
cd apps/admin-web
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_BASE_URL at a running services/api
npm install
npx tsc --noEmit && npx eslint .   # Expect: both clean
npm run dev                        # Expect: ready on http://localhost:3000
# Then actually open it in a browser and click through Tenant List -> Details ->
# Create -> Edit -> Suspend -> Reactivate against a live backend — this has not
# been done yet this session (see §11, §16).
```

---

## Engineering Status

**Completed Sprints:** 0 (Product Blueprint), 1 (Technical Architecture v1.0), 1.5 (TAD remediation → v2.0), 2 (Data Architecture v1.0), 2.6 (Data Architecture remediation → v2.0), 3 (Identity Platform backend), 4.1 Steps 1–2 (Tenant Platform plan + backend).

**In progress:** Sprint 4.1 Step 3 (Tenant Platform frontend) — 6/10 screens, not yet reviewed/approved/browser-verified.

**Completed Commits (18 total on `feature/tenant-platform-frontend`; `main`/`develop` are 3 commits behind, still at `a1f83de`):**

```
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

**Current Milestone:** Sprint 4.1 Step 3 — Frontend implementation for the Tenant Platform. In progress, not complete: 6/10 screens built, not browser-verified, not user-approved.

**Current Feature:** Tenant Platform (Sprint 4.1) — Tenant CRUD/lifecycle, Subscription, Settings, Feature Flags, Tenant Directory, Tenant Administration (backend complete; frontend: List/Details/Create/Edit/Suspend/Reactivate built and unverified, Subscription/Quota/Feature-Flags/Settings deferred).

**Current Module:** Backend — `services/api/src/restaurant_os_api/modules/identity` (extended, not new, per Decision A). Frontend — `apps/admin-web` (Next.js 15 app, scaffolded and partially built this session).

---

*This document should be updated at the end of every session, or whenever a step/commit boundary is crossed, so the next session can resume without re-deriving context.*
