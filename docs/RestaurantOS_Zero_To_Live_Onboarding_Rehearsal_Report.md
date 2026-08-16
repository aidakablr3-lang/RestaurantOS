# RestaurantOS — Zero-to-Live Onboarding Rehearsal Report

**Test environment:** Local Docker rehearsal stack (`restaurantos-rehearsal-api-1` + `restaurantos-rehearsal-postgres-1`, Postgres on host port 5434)
**Git commit under test:** `f441b5d4943706cf48770d252bdc94a0f7e9952b` (branch `develop`, 2026-08-15 12:03:57 +0530)
**Database:** Rehearsal Postgres, isolated from any production data; pre-existing `Grand Palace Hospitality LLC` tenant preserved and confirmed untouched throughout
**Date:** 2026-08-16
**Tester:** Claude (agent), operator-approved, no destructive step taken without explicit confirmation
**Overall result:** **PASS** — a brand-new hotel/pub tenant can be provisioned from zero to a fully operational, RBAC-correct, tax-correct install using only real application APIs and the newly built `create_user.py` operator script. **Zero P0/P1 defects found.** Three real, disclosed gaps remain before this is a fully self-service client-onboarding story (see Gap List).

---

## 1. Purpose and method

This rehearsal proved — end to end, against the real API and a real Postgres database, not mocks — that a disposable tenant ("MysBar", a pub in Mysore) could be taken from zero to a working install using the current deployment/onboarding tooling. Per the governing instructions for this rehearsal:

- Real application APIs/use cases were used throughout, **except** where the existing onboarding procedure explicitly requires a direct database write (the same precedent already established by `backfill_tenant_owner.py` and now `create_user.py` — see §5, Gap 1).
- RBAC was never bypassed at the API layer. The one deliberate, disclosed exception is `create_user.py` itself, which — like `backfill_tenant_owner.py` before it — performs an out-of-band operator action and intentionally bypasses `RoleGrantPolicy`, exactly as that policy's own design allows for operator-authorized actions outside the live API.
- No production business logic was modified.
- All 13 rehearsal steps plus the automated smoke test were tracked to a precise PASS/PARTIAL/FAIL outcome (§2).
- All disposable data was cleanly removed at the end, scoped by `tenant_id`, verified against every one of the 50 tenant-scoped tables before commit (§4).
- The rehearsal was authorized to stop immediately on any P0/P1 defect. None occurred.

## 2. Step-by-step results

| # | Step | Result | Notes |
|---|------|--------|-------|
| 1 | Create new tenant | **PASS** | Real `POST /api/v1/admin/tenants` call, platform-admin token |
| 2 | Create/bootstrap Owner | **PASS** | Via `create_user.py --apply` (see Gap 1 — no API path exists) |
| 3 | Create restaurant + branch | **PASS** | Real API, as Owner |
| 4 | Configure INR + CGST/SGST | **PASS** | Real API; confirmed on the bill as two separate 2.5% tax lines |
| 5 | Create tables | **PASS** | Real API, 3 tables across 1 dining zone |
| 6 | Create menu items | **PASS** | Real API, 1 food category + 1 bar category |
| 7 | Create inventory/recipe | **PASS** | Real API; beverage inventory + recipe only, consistent with the project's own product decision to de-scope food inventory tracking |
| 8 | Create Manager/Waiter/Kitchen Staff via `create_user.py` | **PASS** | 3 accounts created with explicit `--role-name` and `--branch-id` scoping |
| 9 | Verify each user's login + exact permissions | **PASS** | All 4 accounts (Owner, Manager, Waiter, Kitchen Staff) logged in via the real `/api/v1/auth/login` endpoint and returned exactly the expected permission set — no over- or under-grant (§3) |
| 10 | Generate/verify table QR codes | **PASS** | Real API; QR token resolves via `GET /api/v1/qr/{token}` per the documented flat-envelope deviation (ADR 0001) |
| 11 | Run `pilot_smoke_test.py` | **PASS** (14/15 automated checks; 1 false failure explained, see §3.1) | Real HTTP order → kitchen → payment → EOD cycle |
| 12 | Full manual operational path: QR order → waiter/kitchen → serving → inventory → bill → payment → auto table release → EOD | **PASS** | Full walkthrough via real APIs, detailed in §3.2 |
| 13 | Clean removal of disposable test data | **PASS** | Scoped, transactional, verified; Grand Palace tenant confirmed untouched (§4) |

**13/13 rehearsal steps PASS. 0 PARTIAL. 0 FAIL. 0 P0/P1 defects.**

## 3. Evidence detail

### 3.1 Automated smoke test (`pilot_smoke_test.py`)

14 of 15 automated checks passed, including real order creation/firing, KDS ticket generation, payment, automatic table release, and EOD reporting. The one failure — "Alembic migration state" — was **not a product defect**: it failed because the ad-hoc host shell used to invoke the script directly lacked the `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` environment variables that the running API container has set (settings validation fails before Alembic even runs). This was independently verified by running `alembic current` and `alembic heads` **inside** the actual API container:

```
0012 (head)
---HEADS---
0012 (head)
```

Migration state is correctly at head. This is a note for whoever next writes a migration-state check script standalone (set the JWT env vars, or run it inside the container), not a gap in the product itself.

### 3.2 Manual operational path (step 12)

Walked the full guest-to-EOD path on table T1, distinct from the table the automated smoke test used, via real APIs only:

1. **QR resolution** (`GET /api/v1/qr/{token}`) → correct `tenant_id`/`branch_id`/`table_id`.
2. **Guest menu** (`GET /api/v1/qr/{token}/menu`) → correct categories/items/prices.
3. **Guest order** created, 1 food item (Chicken Sliders ×2) + 1 bar item (Whiskey Sour ×1) added, submitted (`POST .../submit`).
4. **Table auto-transition**: `available → occupied` on submit, with no manual status call.
5. **Kitchen/bar station routing**: the single order produced **two separate kitchen tickets** — one `station: "kitchen"` (Chicken Sliders), one `station: "bar"` (Whiskey Sour) — confirmed correct routing.
6. **Kitchen ticket lifecycle**: both tickets progressed `fired → in_progress → ready → served` at both the ticket and item level via `POST /api/v1/kitchen-tickets/{id}/status` and `POST /api/v1/kitchen-items/{id}/status`.
7. **Recipe-driven inventory deduction**: Whiskey stock was queried before (`3000.0000 ml`) and after (`2940.0000 ml`) marking the bar ticket served — exactly 60ml deducted, matching the recipe, and **only** on the "served" transition, not earlier.
8. **Bill generation** (`POST /api/v1/orders/{id}/bill`): subtotal ₹790.00, correctly split into two separate 2.5% tax lines (CGST ₹19.75 + SGST ₹19.75), total due ₹829.50.
9. **Payment** (`POST /api/v1/bills/{id}/payments`, cash, full amount): settled successfully.
10. **Automatic table release**: `occupied → available`, with no manual status call, immediately on payment settlement.
11. **EOD report** (`GET /api/v1/branches/{id}/reports/end-of-day`): `orderCount=2` (this order + the earlier smoke-test order), `itemsSoldCount=4`, `grossSalesAmount=1060.50` — an exact match to `231.00` (smoke test) + `829.50` (this walkthrough), `outstandingAmount=0`.

No discrepancy found anywhere in this chain.

### 3.3 RBAC verification (step 9)

Login and permission resolution were checked for all 4 accounts created via `create_user.py`:

| Role | Scope | Result |
|------|-------|--------|
| Tenant Owner | Tenant-wide | Full 25-permission set, tenant-wide — correct |
| Branch Manager | Branch-scoped | Broad operational access, correctly **excluding** `restaurant.manage`/`branch.manage` (those stay Owner-only) — correct |
| Waiter | Branch-scoped | Exactly order/table/reservation/menu-read — correct |
| Kitchen Staff | Branch-scoped | Exactly `kitchen.manage`/`kitchen.read` + `menu.read` — correct |

No role received more access than intended; no role's grant leaked from `byBranch` into `tenantWide` scope or vice versa.

## 4. Cleanup verification (step 13)

Test data was removed via a single transactional SQL script, scoped by `tenant_id = '01M04RP45QP7JRRD8T8ZZYN73C'` (MysBar) on every statement, covering all 50 tenant-scoped tables. The transaction verified zero remaining rows for that tenant across every table before committing; a first attempt correctly rolled back (nothing committed) when two tables were initially missed from the cleanup list, self-caught by an FK violation rather than silently leaving orphaned data.

Post-cleanup verification:
- MysBar tenant row: **0 rows** (fully removed)
- Grand Palace Hospitality LLC tenant: **untouched** — 4 users, 4 orders, `status: active`, confirmed present after cleanup
- RestaurantOS Platform Ops tenant: untouched

## 5. Gap list — what still prevents a fully self-service first-client installation

These are the same class of finding as the original Phase 0 audit, re-confirmed live in this rehearsal, not new discoveries:

**Gap 1 — No user-creation API or UI exists. FIXED 2026-08-16.** `UserRepository` now has a real `create()` + `list_for_tenant()`, backing a real `POST /api/v1/users` and `GET /api/v1/users` API (`CreateUserUseCase`/`ListUsersUseCase`), gated by the existing `roles.assign` permission (no new permission needed — a bare account has no access until a role is granted, so the capability that matters is already "can this caller grant a role"). A tenant's own Owner can now create staff (waiters, managers, kitchen staff) directly from a new Staff page in admin-web — list, create (with a one-time generated-password reveal dialog), and grant-role UI, all wired to the real API. Verified live in the browser end-to-end: created a staff account through the UI, saw the one-time password dialog, granted it the branch-scoped "Waiter" role through a real role/branch picker, and confirmed the resulting `UserRole` row in Postgres. One real UI bug was found and fixed during this verification: the Role/Branch `<Select>` components were displaying raw ULIDs instead of names (missing the dynamic `items` label-map prop). Backed by 10 new unit tests, 7 new integration tests (real Postgres, RBAC-gated), and 6 new frontend tests (hooks); full regression suites (96 backend integration tests, 175 frontend tests) re-verified passing. `create_user.py` remains necessary for exactly one case the real API structurally cannot cover: bootstrapping a brand-new tenant's very first user, since creating any user requires an authenticated caller who already holds `roles.assign`, and a new tenant has none yet.

**Gap 2 — No hard-delete/purge tooling for a tenant's data. FIXED 2026-08-16.** `POST /api/v1/admin/tenants/{id}/offboard` is still soft-delete only (by design — see its own docstring), so a new `scripts/purge_tenant.py` closes the actual gap: a manually-run, dry-run-by-default operator script (deliberately *not* an HTTP endpoint — an irreversible, tenant-destroying action shouldn't be one bad click or one compromised admin token away) that permanently deletes every row for a tenant. Refuses to run unless the tenant is already `offboarded`, and requires `--confirm-legal-name` matching the tenant's exact stored name (not just its id) as a second confirmation. Discovers every tenant-scoped table dynamically from `information_schema` at run time rather than a hard-coded list, so a future migration adding a new tenant-scoped table is covered automatically — a hard-coded list is exactly the kind of thing that silently goes stale and leaves orphaned data behind after a "purge" that's supposed to guarantee none remains. Uses the same FK-safe retry-convergence technique proven during this rehearsal's own cleanup (§4), but correctly wrapped in per-table `SAVEPOINT`s (`begin_nested()`) so one table's FK violation doesn't roll back rows already deleted from other tables in the same pass. Verified live against real Postgres end-to-end: refused on a wrong `--confirm-legal-name`, refused on a non-offboarded (`active`) tenant, dry-run correctly previewed row counts with zero writes, `--apply` deleted everything and converged in one pass, a second run against the now-gone tenant exited cleanly with nothing to do, and the platform-ops/Grand Palace tenants were confirmed untouched throughout.

**Gap 3 — Idempotency guard not wired into tenant creation. FIXED 2026-08-16.** `POST /api/v1/admin/tenants` now accepts an optional `Idempotency-Key` header and replays the original response on a repeated key, exactly like the 16 other guarded routers. It could not reuse the existing `IdempotencyGuard`/`idempotency_keys` as-is: that table's `tenant_id` column is a hard `NOT NULL` foreign key to `tenants.id`, but tenant creation is the one request that by definition runs before any tenant row exists. Fixed with a new `platform_idempotency_keys` table (migration `0013`) and `PlatformIdempotencyGuard` — no `tenant_id`, no RLS, globally unique on `idempotency_key` alone, used only by pre-tenant platform-admin routes (today: just onboarding). Verified with a new integration test suite (`test_platform_idempotency.py`, mirroring the existing guard's own test coverage) plus 3 new router-level tests (`TestOnboardTenantIdempotency` in `test_admin_tenant_router.py`) proving: a repeated key+body replays the same tenant without duplicating it, the same key with a different body is rejected `409 IDEMPOTENCY_KEY_CONFLICT`, and omitting the header preserves the prior behavior unchanged. Full `test_admin_tenant_router.py` suite (20 tests) and the pre-existing `IdempotencyGuard` suite both re-verified passing with no regressions.

**All three disclosed gaps from this rehearsal are now closed.** No further known gaps block a clean first-client installation as of 2026-08-16.

No other gaps were found in this rehearsal. Table/order/kitchen/billing/inventory/RBAC/EOD logic all behaved correctly under a real end-to-end walkthrough with a genuinely fresh tenant (not a previously-seeded one).

## 6. Appendix — exact field names discovered during this rehearsal

Two of my own script-writing mistakes surfaced real API contract details worth recording so they aren't re-discovered the hard way (by a human or by the deferred onboarding co-pilot):

- `POST /api/v1/auth/login` requires `tenantId` in the request body, not just `email`/`password`.
- `POST /api/v1/bills/{id}/payments` expects `tenderType` (enum: `cash`/`card`/`wallet`), not `method`.
- `AddressRequestSchema` uses `countryCode`, not `country` — an optional field, so a wrong key is silently ignored rather than rejected (no `422`), which can produce a null address field without any visible error. Not fixed here since it wasn't in this rehearsal's critical path, but worth knowing for a future onboarding UI/co-pilot that also sets addresses.

Neither of these is a product defect — both are documented here purely as integration-accuracy notes.
