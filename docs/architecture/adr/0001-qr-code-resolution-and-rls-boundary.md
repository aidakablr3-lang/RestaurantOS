# ADR 0001: QR Code Resolution and RLS Boundary

**Status:** Accepted (Sprint 5 Step 3, approved by user before Step 4)

**Date:** 2026-08-08

**Related:** `RestaurantOS_Restaurant_Platform_Architecture.md` §3.1 (`QRCode` entity spec), §4 (multi-tenancy/RLS), §11 (events), `alembic/versions/0004_restaurant_platform.py` (the `qr_codes` table and its own extensive inline disclosure)

---

## Context

Every other tenant-scoped table in RestaurantOS enforces tenant isolation with a single, uniform mechanism (`RestaurantOS_Restaurant_Platform_Architecture.md` §4.2, `technical-architecture-v2.md`'s own established pattern): Postgres Row-Level Security, `USING (tenant_id = current_setting('app.tenant_id', true))`, backed by `SET LOCAL`/`set_config()` inside every `UnitOfWork` transaction. This is deliberate and load-bearing — it is the hard backstop that makes a missing `WHERE tenant_id = ...` in application code fail closed instead of leaking cross-tenant data.

`QRCode` is architecturally different from every other entity in the catalogue in one specific way: architecture §3.1 states its resolution path is read "by `token` alone" by "an unauthenticated guest scanning a code... before tenant context is known — this is an explicit, narrow exception to 'every query goes through `TenantContext`'". The token itself is what *establishes* tenant/branch/table context; it is not looked up *within* an already-established context, which is the precondition every other query in this codebase can assume.

Migration `0004` (Sprint 5 Step 3) discovered, while implementing and testing this table, that this isn't merely a stylistic exception — it is a structural incompatibility with the standard RLS predicate, documented here formally per the "if an architectural change is required, STOP and create an ADR" rule this project has followed since Sprint 4.1 (`AI_HANDOFF.md` §14).

## Why standard tenant RLS cannot be applied to `qr_codes`

The standard policy is `USING (tenant_id = current_setting('app.tenant_id', true))`. When no tenant context has been set for the current transaction — which is exactly the resolution path's own starting condition, since the token is what will *produce* the tenant context, not consume an existing one — `current_setting(..., true)` returns `NULL`. `tenant_id = NULL` evaluates to `NULL` in SQL, which `USING` treats as "row excluded." This is not a bug in the predicate; it is RLS working exactly as designed. The consequence is that **every** row in the table becomes invisible to that query, including the one row the guest is trying to resolve. There is no tenant-scoped WHERE clause the resolution query could add to work around this, because the whole point of the query is that it doesn't know the tenant yet.

Postgres RLS evaluates only column values and session-local settings — it has no visibility into *which application code path* issued a query. This means a single `USING` predicate cannot simultaneously (a) block an arbitrary unscoped query from seeing another tenant's rows and (b) allow the one specific, reviewed resolution code path to see the row it needs. Those two requirements are in direct tension for this table only, because this table alone has a legitimate, architecture-mandated caller with no tenant context.

## Decision

`qr_codes` has **no RLS policy** (confirmed: `relrowsecurity = false`). This is the same no-RLS treatment `permissions` already received in migration `0003`, for an unrelated reason (pure platform reference data there vs. a structurally-pre-tenant-context read path here) — not a new, third isolation mechanism, matching architecture §4.2's "no second tenant-isolation mechanism is introduced."

Tenant scoping for the **management** read path (the future admin-web "view/revoke this branch's QR codes" screen) is enforced entirely at the application layer: every repository method on `QRCodeRepository` filters `WHERE tenant_id = :tenant_id` explicitly in the query itself, not via a database policy. This was verified by this session's own test suite (`tests/integration/modules/restaurant/test_repositories.py`), which proves cross-tenant isolation is still correct for the management path even without RLS backing it.

**This ADR does not change the current database design.** `qr_codes`' schema, indexes, and constraints are unchanged from migration `0004` as already implemented and approved. This ADR documents and formalizes a decision already made, and sets the requirements the *future* resolution endpoint (Step 4 or later) must satisfy — it does not build that endpoint, and does not introduce any new database role, connection, or bypass infrastructure to work around the RLS gap. (An RLS-bypass role for a single trusted connection was considered and explicitly rejected for now: it would be new infrastructure solving a problem the application layer already solves correctly, and the endpoint that would use it doesn't exist yet.)

## The security boundary the future QR-resolution endpoint MUST implement

The resolution endpoint (`GET /api/v1/qr/{token}` per architecture §11's API table) is **not implemented by this ADR or by Sprint 5 Step 3** — it is Step 4+ scope. When it is built, it must satisfy every requirement below. This ADR exists specifically so that work does not silently reinvent or weaken these constraints.

### What the endpoint may return

Exactly `{tenant_id, branch_id, table_id}` — the three identifiers architecture §11 already specifies, and nothing else. This is a bootstrap response only: it hands the caller the coordinates needed to *begin* an authenticated or guest-scoped session against those three IDs, not any data belonging to them.

### What the endpoint must NEVER expose

- Any `Restaurant`/`Branch` display data (name, address, operating hours) — those require their own, separately-authorized read.
- Any `MenuItem`/`MenuItemBranchPrice`/`MenuItemAvailability` data — menu data has its own read path with its own scoping decision to be made in Step 4, not bundled into resolution.
- Any other tenant's or branch's `QRCode` rows, token values, or existence/non-existence signal beyond "this specific token resolved or it didn't."
- Any RBAC/user/role/permission data.
- Any internal database identifiers beyond the three ULIDs the response contract already names (`qr_codes.id`, `created_at`/`updated_at`, `status` history, etc. must not leak).
- Distinguishing error detail between "token not found," "token revoked," and "token belongs to a permanently-closed branch" — architecture's own database design (`ck_qr_codes_status_is_valid`, soft-delete via `deleted_at`) already models these as distinct states, but the endpoint must collapse all non-resolvable cases to a single generic "not found" response to avoid giving an attacker a state-classification oracle.

### Token validation requirements

- Resolution must query by `token` alone (the existing global `UNIQUE (token)` index), then verify `status = 'active'` and `deleted_at IS NULL` before returning anything — a revoked or soft-deleted code must resolve identically to a token that never existed.
- The lookup itself does not require RLS to be safe, because the query is intentionally global-by-design (per architecture §3.1's uniqueness note: "global, not tenant-scoped, since the token is resolved... before tenant context is known") — the safety boundary here is exact-match token lookup plus the status/deletion check, not tenant filtering.

### Rate limiting requirements

- Must be rate-limited per source IP and, once observed, per token, independent of any per-tenant or per-user rate limit elsewhere in the system (this endpoint has no authenticated caller to key a limit off of).
- Must apply a stricter limit to failed resolutions (token not found / not active) than to successful ones, since failed attempts are the enumeration signal.

### Enumeration / brute-force protections

- Constant-time comparison is not sufficient by itself when the token space is guessable — see the opaque-token requirement below, which is the primary defense.
- Response timing and response shape must be identical for "token does not exist" and "token exists but is revoked/inactive" (see "must never expose" above).
- Repeated failed lookups from a single source must be detectable for the abuse-monitoring requirement below, in addition to being rate-limited.

### Token opacity

`qr_codes.token` MUST be a cryptographically random, non-sequential, non-guessable opaque value — explicitly **not** the row's own ULID `id` (a ULID is time-ordered and partially predictable by design, which is correct for `id` but wrong for a value meant to resist guessing) and not derived from any other visible identifier (table number, branch name, sequential counter). This is a requirement on the *value generation* logic for the token when a `QRCode` is created, not a schema change — the column is already a plain unconstrained `TEXT` (`sa.Column("token", sa.Text(), nullable=False)`), which already accommodates this; no migration is implied by this ADR.

### Audit / abuse-monitoring requirements

- Every resolution attempt (success or failure) should be observable for abuse monitoring — volume from a single IP, volume against a single token, geographic/velocity anomalies — independent of whether it becomes a full `AuditEvent` (architecture §3.1 already flags `QRCode` revocation/regeneration for `AuditEvent` once the audit module exists; resolution *attempts* are a distinct, higher-volume signal better suited to request-level logging/monitoring than the audit trail).
- A spike in failed resolutions against one token should be treated as a signal to consider proactive revocation, independent of any explicit staff action.

### Downstream validation after resolution

Resolution is a **bootstrap step only** — it establishes which `tenant_id`/`branch_id`/`table_id` a subsequent request is about, and confers no elevated trust or authorization beyond that. Every operation that follows resolution must independently pass through the system's existing, unweakened authorization boundaries:

- Any subsequent **authenticated** operation (staff acting on the table, an order being associated with it, etc.) goes through the normal `TenantContext`/RLS/RBAC stack exactly as every other authenticated request does today — the resolved `tenant_id`/`branch_id` from a QR scan carries no special authority and must be re-validated by the normal authenticated request path, never trusted as a bypass.
- Any subsequent **guest-facing** operation (the future Customer/Guest Platform's cart/ordering flow, explicitly out of scope per architecture §2's boundary table) must define its own guest-session authorization model when that platform is designed — this ADR does not define it, only requires that resolution alone never be treated as sufficient authorization for a write.
- The resolved `table_id` must still be validated as belonging to the resolved `branch_id`, and the resolved `branch_id` to the resolved `tenant_id`, using the same FK relationships already enforced by the schema — resolution does not get to skip referential checks other code paths rely on.

## Consequences

**Positive:** The resolution path remains architecturally possible at all, which a naive "just enable RLS everywhere" approach would have silently broken (the query would always return zero rows, failing in a way that looks like "token not found" for every token, forever). The management path keeps real, tested tenant isolation via explicit application-layer filtering, matching the `permissions` table's existing no-RLS precedent rather than inventing something new.

**Negative / accepted risk:** `qr_codes` is the only table in the schema where a missing `WHERE tenant_id = ...` in a future repository method would not be caught by a database-level backstop — unlike every other table, where RLS fails closed even if application code forgets. This is a real, asymmetric risk versus the rest of the schema, accepted because the alternative (RLS enabled) is not merely riskier but non-functional for this table's own defining use case. Mitigation: `test_repositories.py`'s `QRCodeRepository` tests explicitly cover cross-tenant isolation for the management path today, and this must remain true for any future repository method added to this table.

**Deferred, not solved here:** every requirement in "The security boundary the future QR-resolution endpoint MUST implement" is a Step 4+ (or later) implementation obligation. This ADR's job is to make sure that work starts from an explicit, reviewed contract instead of ad hoc decisions made under Step 4's own time pressure.
