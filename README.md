# RestaurantOS

Cloud-native, multi-tenant SaaS platform for restaurants, pubs, bars, cafés, breweries, hotels, and multi-branch chains.

## Status

Architecture-complete, implementation in progress (Sprint 3+). The following documents are **frozen** and constitute the single source of truth for all engineering work:

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

Local development environment setup (Docker Compose) will be added in the infrastructure-scaffold PR that follows this one.
