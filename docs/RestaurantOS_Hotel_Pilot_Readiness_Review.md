# RestaurantOS — Hotel Pilot Readiness Review

**Date:** 2026-08-12
**Scope:** Formal readiness review for a controlled hotel/restaurant pilot, built from the current repository state (`feature/restaurant-platform`, HEAD `64e5b1f` plus uncommitted working-tree changes — see §0), the architecture documents, and the Run 3/Run 4 full-restaurant-day simulation reports.
**Not a feature sprint.** No product code was changed to produce this review.

---

## 0. Repository State At Time Of Review

`git status` shows **118 changed paths** on top of the last commit (`64e5b1f`): 78 modified files and ~40 new (untracked) files, totalling roughly +12,590/-2,972 lines. This is **pre-existing work from an earlier session**, not something this review created. It implements real, working functionality that both the Run 3 and Run 4 simulations exercised successfully: guest-facing QR ordering, kitchen/bar station routing, `OrderItem.served` transitions, recipe-driven inventory deduction (see §2), automatic table-status updates from the order lifecycle, and end-of-day reporting (backend + frontend).

This is flagged as **Finding P1-1** below (§6) — not because the code doesn't work (it does; both simulations verified it against a real backend), but because functionality this significant has never been committed. It exists only in a local working tree.

---

## 1. Table / Order Model — Design Recommendation

### Current behavior (verified directly in code, `create_order.py`)

`CreateOrderUseCase` creates a new `Order` row and unconditionally sets `Table.status = OCCUPIED` whenever a `table_id` is supplied. **It never checks whether the table already has an open, non-terminal order.** There is no uniqueness constraint, no domain invariant, and no application-layer guard preventing a second (or third, or tenth) concurrent `fired`/`open`/`billed` order from being created against a table that already has one. Run 4's own data-integrity check (Test 18) observed this directly: three separate, unrelated test scripts each created an order against table O2 without billing the previous one, and the system allowed all three to coexist.

This did **not** corrupt billing in Run 4 — each order gets its own `Bill`, and each bill settles independently and correctly. The problem is architectural, not transactional: nothing *relates* those orders to one another, and nothing prevents accidental duplication.

### Why this is potentially problematic

- A guest's second round of drinks, entered as a *new* order instead of items added to the existing one, produces two separate bills for one sitting — the guest could be asked to pay twice, or one bill could be forgotten.
- The Tables board / floor plan has no way to show "this table has 3 open orders" vs. "this table has 1" — occupancy is currently a boolean (`occupied`/`available`), not a count or a session.
- There is no supported way to intentionally split a bill across multiple orders at one table (Scenario D below) — the *absence* of structure looks superficially similar to the presence of one, which is the dangerous part.

### Real restaurant scenarios, mapped against the current and existing (but unused) domain model

| # | Scenario | Current system behavior | What's actually needed |
|---|---|---|---|
| A | One table, one group, one order | Works correctly today. | — |
| B | Same table orders again later (second round) | Creates a second, **unrelated** `Order` on the same table. No link to the first. | The two rounds should be able to share one bill, or at minimum be visibly grouped. |
| C | Multiple guests at the same table order at different times (e.g., staggered QR orders) | Each guest's QR submission creates its own `Order`. Same gap as B. | Same as B — grouping, not prevention. |
| D | Split bill (one table, multiple separate checks) | Not supported as a deliberate operation — the only reason this "works" today is the *absence* of any guard, not a designed feature. | A designed split-bill flow, not an accidental side effect of missing validation. |
| E | Multiple running checks (e.g., a bar tab that isn't tied to food) | No concept of a running tab is wired into ordering at all. | This is exactly what the `Tab` entity was built for (see below). |
| F | Order amendment / additional items mid-meal | `AddOrderItemUseCase` already supports adding items to a `fired` order (task #225, verified). This is the *correct* path for "add more food to the same order" and does not need a second `Order`. | Already solved — staff should use this, not create a new order. |
| G | Manager intervention (e.g., merging two accidental orders) | No merge operation exists. | Out of scope for pilot; flag as a known gap. |
| H | Table transfer (moving a party to a different table) | No transfer operation exists; `Order.table_id` has no update path once set. | Out of scope for pilot; flag as a known gap. |
| I | Closing the table | Already correct — full settlement auto-releases the table (P0-verified in Run 4). | — |

### Recommended model: **one active Tab (dining session) per table, containing one or more Order rounds**

This is **not a new invention** — it is already specified in Data Architecture v2.0 Group E and already exists as a real domain entity, database table (migration `0007`), repository, and pair of use cases (`Tab` create/close, verified live in Sprint 7 Step 3). It is simply **not wired into `CreateOrderUseCase` or the frontend**. The `Bill` entity already supports it structurally: `Bill.order_id` **XOR** `Bill.tab_id` (exactly one non-null, enforced by a DB `CHECK` constraint) — the schema was built from day one to bill either a single order (the common case, scenario A) or an entire multi-order Tab (scenarios B/C/D/E).

Rejected alternative — **strict "one order per table"**: too restrictive. It would block scenario B/C/F (legitimate reordering) unless every reorder were forced through `AddOrderItemUseCase` on an already-fired order, which doesn't compose well with kitchen ticket semantics for a second, later round.

Rejected alternative — **leave it as unlimited, unrelated orders** (today's behavior): does not corrupt billing but provides no way to intentionally group or split, and silently permits the accidental-duplicate-order failure mode described above.

### Impact of the recommended fix

- **Order:** `CreateOrderUseCase` gains an optional step — resolve or create an open `Tab` for the table, set `Order.tab_id`. No domain change needed; `Order.tab_id` already exists.
- **Bill:** `GenerateBillUseCase` currently only supports order-based bills (`Bill.tab_id` path is disclosed-but-unbuilt since Step 4). This is the one piece of real new work: a `GenerateTabBillUseCase` (or an extension of the existing use case) that aggregates every order on a Tab into one bill, combining tax lines across orders.
- **Table:** occupancy logic changes from "does this table have any non-terminal order" to "does this table have an open Tab" — a small, mechanical change, not a new concept.
- **KDS/kitchen tickets:** **no impact.** Tickets are already keyed off individual `OrderItem`s, not the table or the bill; a second round simply fires its own tickets, exactly as it does today.
- **Migration:** **none required.** `tabs` table, `Order.tab_id` FK, and `Bill`'s XOR constraint all already exist in the schema (migration `0007`).
- **API:** one new/extended endpoint (Tab-based bill generation); `CreateOrderRequestSchema` likely gains an optional "add to existing tab" vs. "start new tab" distinction, or this is resolved server-side transparently (recommend server-side — simpler for staff, matches the "no invented UI decision the backend can make for you" convention already used elsewhere in this codebase).
- **Frontend:** currently zero Tab UI exists (Step 9.5 explicitly deferred it). Waiter ordering flow needs a lightweight "new round on this table" vs. "new table" distinction; the Bill page needs to handle a Tab-sourced bill's aggregated line items.

### Should this be fixed before pilot?

**No — this is a P2, not a pilot blocker**, provided the two mitigations below are both in place, which they now are:

1. **Staff SOP** (see the User Manual, §5 Table Management and §17 SOPs): staff are instructed to add rounds to the *existing* fired order (`AddOrderItemUseCase` already supports this) rather than opening a second order on an occupied table, and to bill/close one order fully before starting an unrelated new one at the same table.
2. **This finding is disclosed**, not hidden, in both this review and the User Manual's Known Limitations section.

A controlled pilot with trained staff and this documented workaround does not need the Tab-billing feature built first. It should be scheduled as real, scoped work (`GenerateTabBillUseCase` + minimal Tab UI) for the version after the pilot, informed by what the pilot itself teaches about how often staff actually need multi-round billing in practice.

---

## 2. Inventory Auto-Deduction — Status and Recommendation

**Correction to the Run 4 report's framing:** Run 4 correctly observed, *empirically*, that stock did not move after served orders — but reported this as "NOT IMPLEMENTED" without inspecting the code path itself, because the venue used in both simulations seeded every menu item with `recipe_id = NULL`. Direct code inspection for this review found the deduction logic **is implemented** (in the same uncommitted working tree flagged in §0):

`_recipe_deduction.py::deduct_recipe_inventory_for_served_item` is wired into `UpdateKitchenTicketStatusUseCase` and runs automatically whenever a kitchen ticket item transitions to `served`. For each ingredient on the served menu item's current recipe, it posts a real `StockMovement(movement_type=SALE_DEDUCTION)` against the linked `InventoryItem`, re-checks the negative-stock guard (respecting `allow_negative_stock`/its per-item override, so the toggle isn't bypassed for the one place stock is actually consumed by a sale), and publishes `LowStockDetected` on a reorder-point crossing. If a menu item has no `recipe_id`, or its recipe has no ingredients, this is a deliberate silent no-op — not every sellable item needs a bill of materials, and the codebase's own convention disclaims inventing a business rule that would block service over a missing recipe.

**So the accurate status is:** automatic sale-driven inventory deduction is code-complete and correctly gated on recipe configuration, but (a) it exists only in uncommitted code, and (b) it has never been exercised by any menu item that actually has a recipe attached, because none of the demo venues used in Run 3 or Run 4 configured one.

**Known, disclosed limitation, inherited from the architecture doc itself, not this pass:** `Recipe` is tenant-wide, but each `RecipeIngredient` points at one fixed, branch-scoped `InventoryItem`. A recipe shared by a menu item sold at multiple branches will always deduct against whichever branch the recipe's ingredient rows happen to reference, not the branch the order was actually served at. For a single-branch pilot this has no practical effect.

### Recommendation: acceptable to defer configuring recipes for the pilot, with one exception

- **Required before pilot:** commit the uncommitted code (§0) so this functionality is actually in version history and deployable, and run one live integration test with at least one real recipe configured, to close the gap between "code exists" and "verified end-to-end with real data" (Run 4 never exercised this path).
- **Acceptable to defer:** configuring full recipes for every menu item. A hotel pilot's primary goal is validating the order → kitchen → bill → payment → table lifecycle, not inventory accuracy. Most hotel F&B pilots tolerate manual stock counts for the pilot window.
- **Recommended minimum for pilot, not full deferral:** configure recipes for the venue's **highest-volume 2-3 items** (e.g., the top sellers from the EOD report's `topItems`) so the deduction path is exercised with real, live data during the pilot, rather than staying completely dark. This gives the operator a real signal on whether the feature is trustworthy before committing to configuring the entire menu.
- **Do not** claim in the User Manual or to hotel staff that inventory is being tracked automatically for items without a configured recipe — the manual (§15) states this plainly.

---

## 3. Production Deployment Hardening — Root Cause Recap

Run 4 found that the backend process serving requests had not been restarted after a P0 code fix was committed, and that this was only caught because the (deliberately retired) refund route was still visible in the live OpenAPI schema. This is a process/operational gap, not a code defect: **there is currently no startup-verification step that would catch "this running process is not serving the code that's actually in the repository."**

See `docs/RestaurantOS_Pilot_Deployment_Checklist.md` for the full checklist and `scripts/pilot_smoke_test.py` for the executable smoke test built to close this gap directly — it re-checks the OpenAPI schema for exactly the retired-route symptom that caused Run 4's false negative, among other checks.

---

## 4. Formal Findings Register

Severity definitions (as given): **P0** = blocks pilot. **P1** = serious operational issue. **P2** = important improvement. **P3** = cosmetic/documentation.

### P0 — none

No P0 findings. The order → kitchen → bill → payment → automatic table-release lifecycle, RBAC enforcement, overpayment rejection, and financial reconciliation are all verified working against the real system (Run 4).

### P1 findings

**P1-1 — Substantial verified functionality exists only as uncommitted working-tree changes.**
- **Evidence:** `git status` at the time of this review shows 118 changed paths (~12,590 insertions) never committed, implementing guest QR ordering, station routing, `OrderItem.served`, recipe-driven inventory deduction, automatic table-status updates, and end-of-day reporting — all functionality that both Run 3 and Run 4 relied on and verified working.
- **Impact:** this code is not in version history, was never reviewed through this codebase's own established one-logical-commit-per-concern discipline, cannot be reliably deployed (a fresh `git clone` would not have it), and is one `git clean`/lost-workstation away from being gone entirely.
- **Recommendation:** commit this work in logical, reviewed chunks (guest ordering; station routing + served transition + recipe deduction; table auto-status; EOD reporting are natural boundaries, mirroring how every other Sprint 7 step was committed) before pilot. This is a **git action requiring the user's explicit direction** — not performed as part of this review, per the standing instruction not to commit unrelated existing changes without approval.
- **Pilot blocker:** NO (the code works, verified twice), but strongly recommended to resolve before go-live. **Implementation required:** NO (already implemented) — only commit discipline.

**P1-2 — No process-level guarantee that a running backend serves the code actually in the repository.**
- **Evidence:** Run 4's own environment incident (stale uvicorn process serving pre-fix bytecode, undetected until a manual OpenAPI check).
- **Impact:** the exact failure mode that produced Run 4's false-negative on its single most critical test could recur in a real hotel deployment with no built-in detection.
- **Recommendation:** adopt `docs/RestaurantOS_Pilot_Deployment_Checklist.md` and run `scripts/pilot_smoke_test.py` after every deploy/restart.
- **Pilot blocker:** NO, provided the checklist is actually used at go-live. **Implementation required:** NO — checklist and smoke test are delivered by this review (§ below).

**P1-3 — `pydantic-settings` nested-model `env_file` non-inheritance (carried forward, not new).**
- **Evidence:** documented in AI_HANDOFF.md since Sprint 7 Step 9; `DatabaseSettings` never reads `services/api/.env`'s `DATABASE_URL`, only the real process environment.
- **Impact:** a deploy that relies on `.env` alone (rather than exported shell/process environment variables) will silently connect to the wrong database or fail to start correctly — a second possible source of the same class of incident as P1-2.
- **Recommendation:** the deployment checklist's environment-variable step explicitly calls this out; a proper code fix (giving `DatabaseSettings` its own `env_file`) is small and should be scheduled, but is not itself a pilot blocker if the checklist is followed.
- **Pilot blocker:** NO. **Implementation required:** YES (small, not yet done).

### P2 findings

**P2-1 — Multiple concurrent orders can exist on one table with no relationship between them.**
See §1 above for the full design recommendation. **Pilot blocker: NO** (mitigated via SOP + disclosure). **Implementation required:** YES, but deferred to post-pilot (Tab-based billing).

**P2-2 — Recipe-driven inventory deduction has never been exercised end-to-end with real recipe data.**
See §2 above. **Pilot blocker: NO. Implementation required:** NO for the pilot itself; recommended (configure 2-3 top-seller recipes) as a light-touch validation step.

### P3 findings

**P3-1 — Cash Drawer UI has no "currently open drawer" lookup for a branch**, tracked only in local browser state, lost on reload (disclosed in AI_HANDOFF.md Step 9.3). Cosmetic/UX gap, not evaluated further in this review since it was not exercised by either simulation.

**P3-2 — A systemic raw-value `<Select>` label bug** was fixed for Step 9's own new pages but explicitly left unfixed on several pre-existing Sprint 6 pages (modifier groups, reservations, tables, menu item detail, admin tenants) per AI_HANDOFF.md's own disclosure. Cosmetic.

---

## 5. Pilot Readiness Verdict

**CONDITIONAL PILOT READY.**

No P0 findings. Three P1 findings exist, none of which block the pilot outright, but two of them (P1-1, uncommitted code; P1-2, deployment hardening) should be resolved **before go-live**, not just before general release:

1. Commit the pending working-tree work (§0/P1-1) — requires the user's explicit approval and direction on commit grouping.
2. Run the pilot deployment checklist and smoke test (§3, P1-2/P1-3) before the pilot's first live day, and after every restart during the pilot.
3. Brief staff using the User Manual's Table Management section on the multi-order-per-table limitation (P2-1) so it never causes real confusion during the pilot.
4. Decide, before go-live, whether to configure real recipes for the pilot venue's top-selling items (P2-2) — acceptable to skip, but the operator should make that choice knowingly rather than by default.

Everything independently verified by Run 4 (guest ordering, waiter ordering, kitchen/bar routing and FIFO within the tested run, full payment lifecycle including the automatic table-release P0 fix, overpayment rejection, table reuse, billing reconciliation to the penny, RBAC, negative/error handling, EOD reporting, and data integrity) is sound and does not need further work before a controlled pilot.
