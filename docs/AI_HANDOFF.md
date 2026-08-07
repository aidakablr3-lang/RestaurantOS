# RestaurantOS — AI Session Handoff Document

**Purpose:** This is the canonical handoff document for every future Claude session working on RestaurantOS. Read this file first, before touching any code, to reconstruct full project context.

**Last updated:** 2026-08-07
**Updated by:** Repository standardization task (branch restructuring + handoff doc creation)

---

## 1. Current Sprint

**Sprint 4.1 — Tenant Platform** (the first business platform; Product Blueprint Phase 1 / Technical Architecture v2.0 `modules/identity` extension).

## 2. Current Step

**Step 3 — Frontend implementation.** Approved by the user, but not yet started — this session was interrupted to perform repository standardization (branch restructuring + this handoff document) before any frontend code is written.

Sprint 4.1 follows a 5-step gated process, defined explicitly by the user:

| Step | Description | Status |
|---|---|---|
| 1 | Explain implementation plan, wait for approval | Complete — approved, including 3 explicit architecture-compliance decisions (see §11 Known Issues / Decisions) |
| 2 | Implement backend, wait for approval | Complete — 7 commits, approved |
| 3 | Implement frontend, wait for approval | **Not started** — approved to begin, blocked on this repo-standardization task |
| 4 | Testing, wait for approval | Not started |
| 5 | Documentation, wait for approval | Not started |

## 3. Current Milestone

Backend for the Tenant Platform is complete and merged to history (not yet to `main` via PR — see §9 Current PR). Frontend (`apps/admin-web`) has not been scaffolded yet — no Next.js project exists on disk at `apps/admin-web` beyond the empty placeholder from the Sprint 3 monorepo scaffold.

## 4. Repository Path

```
C:\Users\prash\Documents\RestaurantOS
```

This is both the Git repository root and the monorepo root (`services/api`, `apps/`, `packages/`, `infrastructure/`, `docs/`).

## 5. Git Branch

**Current branch:** `feature/tenant-platform-frontend`

Branch structure (created in this repo-standardization task):

```
main                                 <- renamed from master
 └── develop                         <- created from main
      └── feature/tenant-platform-frontend   <- created from develop, currently checked out
```

All three branches point at the same commit as of this writing (no divergence yet — `develop` and the feature branch were just cut).

## 6. Current HEAD Commit

```
174725802f6c998be403a736dbedc2c8c230aab9
```
(short: `1747258` — `feat(identity): add Tenant Administration REST API`)

## 7. Working Tree Status

Clean immediately before this document's own commit. After this document is committed, the tree returns to clean on `feature/tenant-platform-frontend`. Verify with `git status` (see §14).

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

## 9. Current Work

Repository standardization (this task): branch rename/creation, this handoff document. **No frontend code has been written.** No architecture or backend files were touched in this task.

## 10. Next Task

Resume Sprint 4.1 Step 3 (Frontend), starting with scaffolding `apps/admin-web` as a Next.js 15 / React 19 / TypeScript / Tailwind / shadcn/ui / Zustand / TanStack Query / React Hook Form + Zod application, per Technical Architecture v2.0. Per the approved Step 1 plan, the remaining commit sequence is:

- `chore(admin-web): scaffold Next.js admin-web app`
- `feat(admin-web): tenant list, details, and create/edit flows`
- `feat(admin-web): subscription status and quota dashboard`

## 11. Pending Tasks / Known Issues

**Pending (scheduled, not defects):**
- Sprint 4.1 Step 3 — Frontend (not started)
- Sprint 4.1 Step 4 — Formal automated test suite for the Tenant Platform backend (unit + integration + API + security tests as pytest cases; the backend was verified via hands-on scripted checks during implementation, documented in each commit message, but no permanent pytest files exist yet for Sprint 4.1 — Sprint 3's 44 tests are unaffected and still pass)
- Sprint 4.1 Step 5 — Documentation (identity module README needs a Tenant Platform section)

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
- **Sprint 4.1 (Tenant Platform):** No formal pytest suite yet (Step 4, pending). Verified during implementation via hands-on scripts against in-memory fakes and FastAPI's `TestClient` — full lifecycle, security (403 on non-admin), subscription/quota/settings/feature-flag logic, and validation paths all confirmed working; evidence recorded in each commit's message. These scripts were run from the scratchpad directory and are **not** part of the committed test suite.
- **Lint/compile:** `ruff format`, `ruff check`, and `python -m py_compile` all clean as of HEAD.

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
# Expect: 174725802f6c998be403a736dbedc2c8c230aab9

# Re-run the existing backend test suite (from services/api)
cd services/api
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy python -m pytest tests/unit -q
# Expect: 44 passed

# Inspect the current migration state (dry-run, no DB required)
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db" python -m alembic upgrade head --sql
```

---

## Engineering Status

**Completed Sprints:** 0 (Product Blueprint), 1 (Technical Architecture v1.0), 1.5 (TAD remediation → v2.0), 2 (Data Architecture v1.0), 2.6 (Data Architecture remediation → v2.0), 3 (Identity Platform backend), 4.1 Steps 1–2 (Tenant Platform plan + backend).

**Completed Commits (14 total on `main`/`develop`/`feature/tenant-platform-frontend`, all three currently identical):**

```
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

**Current Milestone:** Sprint 4.1 Step 3 — Frontend implementation for the Tenant Platform.

**Current Feature:** Tenant Platform (Sprint 4.1) — Tenant CRUD/lifecycle, Subscription, Settings, Feature Flags, Tenant Directory, Tenant Administration (backend complete, frontend pending).

**Current Module:** Backend — `services/api/src/restaurant_os_api/modules/identity` (extended, not new, per Decision A). Frontend — `apps/admin-web` (not yet scaffolded).

---

*This document should be updated at the end of every session, or whenever a step/commit boundary is crossed, so the next session can resume without re-deriving context.*
