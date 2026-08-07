# Identity Module

Owns authentication and the source-of-truth for authorization data (tenants, users, sessions — roles/permissions land in a follow-up PR, see [Scope](#scope)). Every other module depends on this one; it depends on no other module (Technical Architecture v2.0, module relationship map).

## Layout

```
identity/
├── domain/           # Entities, value objects, exceptions, repository ports — no framework imports
├── application/       # Use cases (login/refresh/logout), DTOs, port interfaces for hashing/tokens
├── infrastructure/    # SQLAlchemy models + repositories, Argon2id + JWT implementations
├── presentation/      # FastAPI router, Pydantic schemas, DI providers
└── public/            # This module's contract for other modules — empty until one exists (Group E)
```

## What's implemented

- **Login** (`POST /api/v1/auth/login`): email + password, tenant-scoped. Returns an access/refresh token pair.
- **Refresh** (`POST /api/v1/auth/refresh`): rotates the refresh token; the rotated-out token is immediately invalid.
- **Logout** (`POST /api/v1/auth/logout`): revokes one session by its refresh token. Idempotent.

Access tokens carry identity claims only (`sub`, `tenant_id`, `session_id`, `device_id`, `permission_version`) — no roles or permissions, per Technical Architecture v2.0 Group C. A caller's current permission set is meant to be resolved per-request against the live `permission_version`, not trusted from the token.

## Scope

Deliberately **not** in this PR:

- **Role/Permission/RolePermission/UserRole** — `UserRole`'s optional branch-scoping depends on the Restaurant module's `branches` table, which doesn't exist yet; RBAC (authorization) has no consumer until a protected, non-auth route exists. Tracked as a follow-up PR.
- **Authentication middleware** for protected routes (decoding an access token on incoming requests) — no protected route exists yet to require it.
- **PIN-based terminal auth** (Technical Architecture v2.0's shared-device profile) — a distinct flow from email/password login with its own lockout/rate-limiting requirements; a separate PR.
- **Redis-backed `permission_version` caching** (Technical Architecture v2.0 Group C's sub-second revocation propagation) — the schema column and the bump mechanism exist (`UserRepository.bump_permission_version`); the Redis cache-aside layer in front of it is an independent, addable-later optimization, not required for correctness of what this PR ships.

## Testing

- `tests/unit/modules/identity/` — no network or database required.
- `tests/integration/modules/identity/` — requires `TEST_DATABASE_URL` pointed at a real PostgreSQL 17 instance; runs the actual Alembic migration (including Row-Level Security policies) rather than `Base.metadata.create_all`, and includes a dedicated test proving RLS itself blocks cross-tenant reads, independent of this module's own application-layer filtering.
