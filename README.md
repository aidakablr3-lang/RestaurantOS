# RestaurantOS

Cloud-native, multi-tenant SaaS platform for restaurants, pubs, bars, cafés, breweries, hotels, and multi-branch chains.

## Status

Architecture-complete, implementation in progress. Identity/auth (Sprint 3) is done. The Tenant Platform (Sprint 4.1) — tenant lifecycle, subscription, settings, feature flags, and a platform-admin frontend (`apps/admin-web`) for Tenant List/Details/Create/Edit/Suspend/Reactivate — is implemented, browser-verified against a real backend, and covered by 84 backend tests (unit + integration) and a 24-spec Playwright end-to-end suite, all passing. See [`docs/AI_HANDOFF.md`](docs/AI_HANDOFF.md) for the full session-by-session history and current state.

The following documents are **frozen** and constitute the single source of truth for all engineering work:

| Document | Path |
|---|---|
| Product Blueprint | [`docs/architecture/product-blueprint.md`](docs/architecture/product-blueprint.md) |
| Technical Architecture v2.0 | [`docs/architecture/technical-architecture-v2.md`](docs/architecture/technical-architecture-v2.md) |
| Enterprise Data Architecture v2.0 | [`docs/architecture/data-architecture-v2.md`](docs/architecture/data-architecture-v2.md) |

Superseded v1.0 drafts and their review reports are retained under `docs/architecture/superseded-*.md` for historical/decision-record purposes only — they are not authoritative.

Architecture Decision Records live in [`docs/architecture/adr/`](docs/architecture/adr/).

## Repository Structure

```
restaurant-os/
├── apps/            # Deployable client surfaces (admin-web, customer-ordering, kitchen-display, mobile)
├── services/        # Deployable backend processes (api, worker, websocket)
├── packages/        # Code shared across two or more apps/services
├── infrastructure/  # Docker, nginx, monitoring, ops scripts
├── docs/            # Architecture documents and ADRs
└── .github/         # CI/CD workflows, issue/PR templates
```

See `technical-architecture-v2.md` §3 for the full folder-structure rationale.

## Engineering Rules

- Never modify the frozen architecture documents to fit an implementation shortcut — if an implementation reveals a genuine gap, raise an ADR.
- Every module follows the bounded-context layering defined in the Technical Architecture v2.0 (`domain` → `application` → `infrastructure` → `presentation`, cross-module access only via a module's `public/` contract).
- Every feature ships with unit + integration tests and, where behavior changes, updated documentation.
- Conventional Commits. See `CONTRIBUTING.md` (to be added) for the full workflow.

## Getting Started

```bash
docker compose up
```

Brings up PostgreSQL + the API (`services/api`), migrated and hot-reloading, on `http://localhost:8000`. Then, for the frontend:

```bash
cd apps/admin-web && cp .env.local.example .env.local && npm install && npm run dev
```

Open `http://localhost:3000`. See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for the full guide — including a Docker-free manual setup, seeding a platform-admin user to log in with, running the test suites (backend unit/integration, frontend typecheck/lint/build, Playwright end-to-end), and troubleshooting.

## API Documentation

`services/api` serves interactive docs at `/docs` (Swagger UI) and `/redoc` when running, and its raw OpenAPI schema at `/openapi.json`. A generated snapshot is committed at [`docs/api/openapi.json`](docs/api/openapi.json) for review/tooling use without a running server — see [`docs/api/README.md`](docs/api/README.md) to regenerate it.

## Contributing

- Conventional Commits for every commit message.
- Every feature ships with tests and, where behavior changes, updated documentation — see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for how to run them.
- Before opening a PR or cutting a release, see [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md).
- CI (`.github/workflows/ci.yml`) runs backend lint/typecheck/tests, frontend typecheck/lint/build, and the Playwright end-to-end suite on every push and PR to `main`/`develop`.
