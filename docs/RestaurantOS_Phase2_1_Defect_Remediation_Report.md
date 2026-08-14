# RestaurantOS — Phase 2.1 Defect Remediation Report

| | |
|---|---|
| **Date** | 2026-08-14 |
| **Scope** | Fix ONLY the two approved defects from Phase 2, plus focused regression testing |
| **Environment** | Local disposable dev environment — real PostgreSQL 17, real backend (FastAPI/uvicorn), real frontend (Next.js), no mocks for regression |
| **Branch** | `develop` (working tree, uncommitted per explicit instruction) |
| **Overall Verdict** | 🟢 READY FOR NEXT PILOT-HARDENING PHASE |

---

## 1. Summary

Phase 2 (the full restaurant-day operational simulation) found two real, live-reproduced defects and explicitly deferred fixing them pending approval. This phase fixes both, and only both — no new features, no unrelated refactoring, no business-logic changes beyond what each defect required.

| Defect | Severity | Status |
|---|---|---|
| #1 — Multi-order table release | HIGH | **FIXED** |
| #2 — EOD Gross Sales over-inclusion | MEDIUM-HIGH | **FIXED** |

---

## 2. Defect #1 — Multi-order table release

### Root cause

`services/api/src/restaurant_os_api/modules/operations/application/use_cases/_table_release.py`'s shared `release_table_if_occupied` helper only ever checked the table's own current status:

```python
async def release_table_if_occupied(table_repository, tenant_id, table_id):
    table = await table_repository.get_by_id(tenant_id, table_id)
    if table is not None and table.status == TableStatus.OCCUPIED:
        table.status = TableStatus.AVAILABLE
        await table_repository.update(table)
```

It had zero awareness of *other* orders against the same table. Phase 2 live-reproduced the consequence: paying off the first of two orders on a table released it to `available` while the second order was still open and unpaid — a new party could be seated at a table with a genuinely outstanding unpaid bill.

### Investigation (before any code was touched)

- Traced every place that can occupy/release a table, close an order, settle a bill, or void an order.
- Found exactly 3 callers of `release_table_if_occupied`: `RecordPaymentUseCase` (on full payment), `CloseOrderUseCase`, `VoidOrderUseCase` — all three already hold `order_repo` locally at the call site, via existing constructor dependencies.
- Confirmed the exact `OrderStatus` state machine (`OPEN → FIRED → SERVED → BILLED → CLOSED`, with `VOIDED` as an alternate terminal path from `OPEN`/`FIRED`) directly from `order.py` — no guessed semantics.
- Confirmed `SQLAlchemyOrderRepository.update()` executes its `UPDATE` immediately in-transaction (Core-style statement, not deferred ORM autoflush), so a same-transaction "any other active orders?" query issued after the current order's own status update correctly sees that update — no need to explicitly exclude the current order's own id.

### Fix (smallest safe change; no new entity, no `Tab` model, no schema change)

1. Added `has_active_orders_for_table(tenant_id, table_id) -> bool` to the `OrderRepository` Protocol — "active" defined as status **NOT IN** `{CLOSED, VOIDED}`.
2. Implemented in `SQLAlchemyOrderRepository`: a single indexed `WHERE table_id = ... AND status NOT IN (...) LIMIT 1` existence check — `table_id` is a direct column on `orders`, no join required.
3. Implemented identically in the `InMemoryOrderRepository` unit-test fake.
4. Extended `release_table_if_occupied` to accept `order_repository` and only release the table when `has_active_orders_for_table` returns `False`.
5. Updated the 3 existing call sites to pass `order_repo` through — no new dependency-injection wiring was needed anywhere.

### Tests

**Unit (in-memory fakes):**
- `test_settling_one_of_two_orders_on_the_table_leaves_it_occupied`
- `test_settling_the_last_active_order_on_the_table_releases_it`
- `test_a_voided_sibling_order_does_not_block_release`
- `test_an_active_order_on_a_different_table_does_not_block_release`
- `test_closing_one_order_leaves_the_table_occupied_when_a_sibling_is_still_active`
- `test_voiding_one_order_leaves_the_table_occupied_when_a_sibling_is_still_active`
- `TestHasActiveOrdersForTable` (5 tests): active order detected; closed order excluded; voided order excluded; tenant isolation; table isolation

**Integration (real Postgres, real HTTP):**
- `test_a_second_order_on_the_table_keeps_it_occupied_until_both_settle` — two independent orders against one table, first settled → table stays `occupied`, second settled → table becomes `available`.

All pass. Full backend suite (1236 tests) confirmed no regressions elsewhere.

---

## 3. Defect #2 — EOD Gross Sales over-inclusion

### Root cause

`get_end_of_day_report.py` computed `gross_sales_amount` from **every non-voided order** opened in the window, regardless of whether it had ever been served or billed:

```python
active_orders = [o for o in orders if o.status != OrderStatus.VOIDED]
gross_sales_amount = sum(o.subtotal_amount + o.tax_amount for o in active_orders)
```

An order still sitting in `OPEN` or `FIRED` — never served, no bill ever raised — counted toward Gross Sales. Phase 2 live-reproduced an inflated gross-sales figure directly traceable to still-open test orders.

### Investigation (before any code was touched)

- Read the existing report schema, API contract, frontend usage, and the use case's own docstring to determine what "Gross Sales" and "Total Collected" were actually intended to mean before changing anything.
- Confirmed via the existing unit test suite's own fixture defaults (`_order()` defaults to `status: SERVED`) that the fix would not break existing tests — `SERVED` already belongs in the "realized" set.
- Considered `BillRepository.get_by_order_id` as an alternative "has this order been billed" signal; set aside in favor of the simpler, unambiguous `order.status`-based approach (avoids N+1 queries and the `close()`-without-billing ambiguity, since `close()` deliberately also accepts `FIRED`/`SERVED` as valid predecessors for orders with no dine-in billing step).

### Fix

- Redefined the "realized" order set for `gross_sales_amount` to `status in {SERVED, BILLED, CLOSED}` — directly matching the required definition, "value of completed/served/billed sales."
- For internal consistency, `items_sold_count`/`top_items` are now also scoped to items belonging to that same realized-order set (previously filtered only by item line-status, independent of the parent order's status — the same family of over-inclusion bug, since an item on a never-fired `OPEN` order could count as "sold").
- Added a new field, `outstanding_amount` — sum of `subtotal_amount + tax_amount` for orders currently `BILLED` in the window (a bill exists, not yet fully paid; full payment transitions `BILLED → CLOSED`). Uses only `order.status`, already fetched — no new repository dependency, no invented accounting semantics.
- `order_count` deliberately still counts every non-voided order regardless of status — a traffic/count metric, not a revenue claim. Unchanged.
- Gross Sales and Total Collected remain deliberately distinct — never conflated, per the explicit requirement.

### Schema/DTO/Frontend changes

- `EndOfDayReportDTO` / `EndOfDayReportResponseSchema` / router mapping: added `outstanding_amount`.
- `apps/admin-web/src/types/report.ts`: added `outstandingAmount: string`.
- `apps/admin-web/.../reports/page.tsx`: added an "Outstanding" `StatCard` between Net Collected and Items Sold.
- `reports-page.test.tsx`: updated fixture and assertion for the new field.

### Tests

**Unit (in-memory fakes), 6 new, covering the required matrix:**
- `test_a_never_served_open_order_does_not_inflate_gross_sales`
- `test_a_billed_but_unpaid_order_counts_toward_gross_sales_and_outstanding`
- `test_a_fully_paid_closed_order_is_not_outstanding`
- `test_a_partially_paid_billed_order_stays_outstanding`
- `test_mixed_order_states_produce_correct_gross_sales_outstanding_and_voided_totals` (closed+billed+open+voided together, all totals verified simultaneously against hand-calculated values)

Plus all 9 pre-existing EOD tests, unaffected (their fixture defaults already sat inside the realized set).

**Integration (real Postgres, real HTTP):**
- `test_a_never_served_order_is_excluded_and_a_billed_unpaid_order_is_outstanding`

All pass.

---

## 4. Regression Results

| Check | Result |
|---|---|
| Backend unit + integration (real Postgres) | **1236/1236 passed** (~82 min) |
| Frontend `tsc --noEmit` | Clean |
| Frontend `eslint` | Clean |
| Frontend `vitest run` (reports page) | 4/4 passed |
| Frontend production build | Clean, 17/17 pages |

### Shortened real operational-flow regression (live, not just pytest)

Run against a real `uvicorn` backend, real Postgres, and — for the final check — a real browser loading the actual `/reports` page as a freshly-seeded regression user. No mocks.

1. Table → Order 1 → Serve → Bill → Pay → **table confirmed `occupied`** (Order 2 still open on the same table).
2. Same Table → Order 2 → Serve → Bill → Pay → **table confirmed `available`** only now.
3. EOD report checked against hand-calculated totals:
   - Gross Sales `30.0000` = Net Collected `30.0000` (20.00 + 10.00 across the two orders)
   - Outstanding `0`
   - Order count `2`
   - Exact match.
4. Independently re-confirmed by loading the live `/reports` page in a real browser: "Outstanding — 0 USD" rendered correctly, all other figures matched the API response exactly. (Pixel screenshot not captured — same disclosed Browser-pane compositing limitation as Phase 2; DOM/text evidence substituted, as before.)

### Incidental environment-config finding (not an application defect, disclosed not silently patched)

`JWTSettings` and `DatabaseSettings` are nested `pydantic-settings` `BaseSettings` subclasses that do **not** carry their own `env_file=".env"` — only the outer `Settings` class does. This means `services/api/.env`'s `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, and `DATABASE_URL` were silently inert unless *also* exported as real process environment variables. This is the actual root cause of the previously-logged, previously-unresolved "Postgres uvicorn auth mismatch" from the Phase 1 pilot readiness review. Left as-is (fixing pydantic-settings' nested-model env-file inheritance is outside this phase's approved scope) — documented here as the workaround future sessions should use: export the three variables as real shell environment variables before running the backend, tests, or Alembic locally.

---

## 5. Remaining Known Limitations (unchanged, out of scope this phase)

- Menu-item time-windowed `MenuItemAvailability` overrides not enforced at order-item-add time (pre-existing, self-disclosed in Phase 2).
- No user-creation API.
- No dedicated bar KDS view.
- No unified `Tab` entity — each round is its own independent `Order` (now safely so, per Defect #1's fix).
- No idempotency keys on the order/payment write paths.
- Tax handling is single-flat-rate only.
- No payment gateway integration.
- Refund workflow route removed from the live API surface.
- No new reporting modules beyond End-of-Day.
- Not deployed anywhere beyond this disposable local environment.

These were explicitly out of scope for this phase ("DO NOT FIX THESE IN THIS PHASE") and remain disclosed, not silently addressed.

---

## 6. Verdict

- **DEFECT #1: FIXED**
- **DEFECT #2: FIXED**
- **Regression: PASS**
- **Overall: 🟢 READY FOR NEXT PILOT-HARDENING PHASE**

No commits were made this phase, per explicit instruction. All production-code, test, and documentation changes remain in the working tree for review — see the accompanying `git status` / `git diff --stat` / `git log` output in the session's final report.
