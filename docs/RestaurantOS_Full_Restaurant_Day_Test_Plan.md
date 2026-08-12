# RestaurantOS — Full Restaurant Day Test Plan

**Status:** Planning document only. No simulation has been executed against this plan yet.
**Branch:** `feature/restaurant-platform` (PR to `develop` open, not merged)
**Prepared:** 2026-08-12
**Supersedes:** informal scripted simulation run earlier in Sprint 7 (see `RestaurantOS_Full_Restaurant_Day_Mock_Test_Report.pdf`, not committed to the repo). This document formalizes that exercise into a repeatable, stage-by-stage plan and corrects it against the current state of the codebase as of this branch.

## 1. Purpose

Define a realistic, end-to-end mock trading day for a fictional venue, broken into discrete, independently verifiable stages, so that a future simulation run (or a human QA pass) can execute against the **real** RestaurantOS backend and admin-web frontend and produce honest, evidence-backed PASS/FAIL results — not a narrative of what the system is *supposed* to do.

This document does not implement anything. It is scoped strictly as a test plan, per explicit instruction. Every stage below is graded **IMPLEMENTED AND TESTABLE NOW**, **PARTIALLY IMPLEMENTED**, or **NOT YET IMPLEMENTED / EXPECTED TO FAIL**, based on direct source-code inspection of this branch (`services/api/src/restaurant_os_api/modules/operations` and `modules/restaurant`, plus `apps/admin-web`), not on architecture-document intent.

## 2. Assumed Venue

| Field | Value |
|---|---|
| Restaurant | The Rooftop Bar & Kitchen |
| Branch | Downtown Rooftop |
| Dining areas | Indoor, Outdoor, Rooftop |
| Tables | I01–I04 (2/4/4/6 seats), O01–O04 (2/4/6/8 seats), R01–R05 (4/4/6/6/8 seats) |
| Menu | Starters, Mains, Pizza, Burgers, Indian, Desserts, Soft Drinks, Beer, Cocktails, Mocktails — food routed conceptually to Kitchen, drinks to Bar |
| Staff | Manager (Restaurant Manager role), 2 Waiters, Kitchen Staff, Bartender, Cashier, Inventory Manager |

All of the above (restaurant/branch/dining-area/table/menu/RBAC-role creation) is **IMPLEMENTED AND TESTABLE NOW** — verified directly in the earlier scripted run against this same backend.

## 3. Capability Legend

- **✅ IMPLEMENTED AND TESTABLE NOW** — real code path exists end-to-end (API and, where relevant, UI); expect a genuine PASS.
- **🟡 PARTIALLY IMPLEMENTED** — part of the flow works; a specific sub-step will not.
- **❌ NOT YET IMPLEMENTED / EXPECTED TO FAIL** — no code path exists; the simulation must record this as a gap, not attempt a workaround that fabricates the missing behavior.

This legend is a prediction based on current source, stated up front so the eventual simulation report cannot be accused of moving the goalposts after the fact. The simulation's job is to *confirm or correct* these predictions with live evidence, not to assume them.

## 4. Pre-conditions

1. Local Postgres running (dev instance, port 5433 in this environment), migrations `0001`–`0008` applied.
2. `services/api` running with `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`/`DATABASE_URL` exported.
3. `apps/admin-web` running against that backend.
4. A seeded tenant + Tenant Owner user (existing E2E fixture tenant is sufficient).
5. Venue data from §2 created (restaurant, branch, dining areas, tables, menu, RBAC test users).
6. Working, functioning screenshot capture confirmed *before* the run starts — the earlier simulation lost this capability mid-session and had to substitute DOM/API evidence with the user's explicit sign-off. Confirm the Browser pane can screenshot successfully as step zero, so evidence isn't compromised again.

## 5. Stage-by-Stage Test Plan

---

### Stage 1 — Customer scans QR code at an indoor table

**Grade: 🟡 PARTIALLY IMPLEMENTED**

| Field | Detail |
|---|---|
| Actor | Guest (indoor table I01) |
| Starting state | Table I01 exists, has a generated QR code (`GET /api/v1/tables/{id}/qr-codes` / `POST` to generate) |
| Action | Guest scans the QR code with their phone camera |
| Expected UI | ❌ **None exists.** There is no guest-facing ordering page anywhere in `apps/admin-web`. Scanning the code today would resolve to raw JSON via `GET /api/v1/qr/{token}`, not a menu page. |
| Expected API request | `GET /api/v1/qr/{token}` — real, unauthenticated, resolves token → tenant/branch/table context. This part is implemented and was verified live in the earlier run. |
| Expected backend state | No state change; a resolution is a read. |
| Expected DB state | No change. |
| Expected result | **PASS** for token resolution only. **FAIL / NOT IMPLEMENTED** for "guest sees a menu and can order" — that surface does not exist. |
| Evidence to capture | Raw `GET /qr/{token}` response body; a screenshot/DOM snapshot of what a guest would actually see (nothing — confirm and document the absence, do not simulate a page that doesn't exist). |
| Potential failure conditions | None beyond the known gap — this is not a bug, it's a missing feature already disclosed in the Sprint 7 report. |

---

### Stage 2 — Customer orders food and drinks (via QR)

**Grade: ❌ NOT YET IMPLEMENTED / EXPECTED TO FAIL (as a guest flow)**

Since Stage 1 has no guest ordering UI, there is no real way for a guest to place an order themselves. The only way to exercise the *order pipeline* for this channel is the same substitution used in the earlier simulation: a staff member opens the order via the real API/UI with `orderSource: "qr"`, explicitly logged and labeled as a simulation of what a guest-placed order would eventually look like, never presented as a real guest interaction.

| Field | Detail |
|---|---|
| Actor | Staff member, simulating a QR-channel order on the guest's behalf |
| Starting state | Table I01 available |
| Action | `POST /api/v1/branches/{id}/orders` with `orderSource: "qr"`, `tableId` = I01; then `POST /api/v1/orders/{id}/items` for each item |
| Expected UI | Staff-side "New order" dialog in admin-web supports selecting `orderSource: qr` manually — this exists and is testable. |
| Expected API request | As above — both endpoints are real and implemented. |
| Expected backend state | `Order` created with `status=open`, then items added with `OrderItemLineStatus=added`. |
| Expected DB state | New row in `orders`, new rows in `order_items`. |
| Expected result | **PASS** for the order-pipeline mechanics; the *channel authenticity* (was this really the guest, unattended) is **NOT TESTABLE** and must be reported as such, not glossed over. |
| Evidence to capture | Request/response JSON; explicit note in the report that this is a staff-simulated QR order. |
| Potential failure conditions | None expected on the mechanical path — this exact flow was already exercised successfully in the earlier run. |

---

### Stage 3 — Another customer orders through a waiter

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW**

| Field | Detail |
|---|---|
| Actor | Waiter (real RBAC-scoped staff user, `waiter` role, `orders.manage` at branch scope) |
| Starting state | Table O02 (outdoor) available |
| Action | Waiter logs into admin-web, opens a new order against O02, adds items through the real "Add item" UI |
| Expected UI | Orders page → "New order" → table select → item picker. This is the real, working staff ordering surface (there is no separate "waiter app" — admin-web *is* the waiter's tool). |
| Expected API request | `POST /branches/{id}/orders` (`orderSource: pos`), `POST /orders/{id}/items` per item |
| Expected backend state | `Order.status = open`, items `status = added` |
| Expected DB state | Row in `orders`, rows in `order_items` |
| Expected result | **PASS** — this is the best-tested path in the whole system. |
| Evidence to capture | DOM snapshot of the order detail page after items are added; API trace. |
| Potential failure conditions | RBAC misconfiguration on the waiter test user (wrong branch grant) would surface as 403 — verify role grant first if this happens. |

---

### Stage 4 — Another order comes from an outdoor table

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW** — mechanically identical to Stage 3, different table (O03). No new capability being tested; included for realism/volume and to exercise concurrent-order handling across dining areas.

---

### Stage 5 — Another order comes from the rooftop

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW** — mechanically identical to Stage 3, table R01. Same note as Stage 4.

---

### Stage 6 — Multiple orders arrive close together

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW**

| Field | Detail |
|---|---|
| Actor | Multiple staff / scripted burst |
| Starting state | Several tables available across all three areas |
| Action | 4–6 orders opened and fired within a short window |
| Expected API request | Same order/item endpoints, issued in quick succession |
| Expected backend state | Each order processed independently; no cross-order interference expected (no shared mutable state observed in `OrderRepository`/`KitchenTicketRepository`) |
| Expected result | **PASS** — already exercised in the earlier run (16 orders opened in a single burst phase with no errors). |
| Evidence to capture | Timestamps on each order's `created_at` vs. kitchen ticket `created_at`, to set up Stage 8's FIFO check. |
| Potential failure conditions | A race condition on ticket ordering would be the only realistic failure mode; not observed previously, but worth re-confirming under a larger burst than last time. |

---

### Stage 7 — Kitchen and bar receive the appropriate items

**Grade: ❌ NOT YET IMPLEMENTED / EXPECTED TO FAIL (as station-separated routing)**

| Field | Detail |
|---|---|
| Actor | System (kitchen ticket generation on fire) |
| Starting state | Orders with mixed food + drink items, fired |
| Action | `POST /orders/{id}/fire` |
| Expected UI | A bar-specific KDS view filtering to drink items only |
| Expected API request | `POST /orders/{id}/fire` → creates `KitchenTicket` |
| Expected backend state | **Every ticket is hardcoded to `station: "kitchen"`** (`fire_order.py::_DEFAULT_STATION`). There is no bar queue; a Mojito and a Chicken Biryani land on the exact same ticket list with no distinguishing field a UI could filter on. |
| Expected DB state | `kitchen_tickets.station = 'kitchen'` for every row, regardless of item contents |
| Expected result | **FAIL / NOT IMPLEMENTED.** The schema supports a real per-ticket station value; the application layer never assigns anything but the default. Confirmed by source inspection and by every ticket observed in the earlier run. |
| Evidence to capture | `GET /kitchen-tickets` response showing `station: "kitchen"` on a ticket that contains only drink items. |
| Potential failure conditions | N/A — this is a confirmed, not merely suspected, gap. |

---

### Stage 8 — KDS shows orders in a sensible FIFO operational queue

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW**

| Field | Detail |
|---|---|
| Actor | Kitchen staff viewing the KDS board |
| Starting state | Several orders fired in a known sequence |
| Action | Fire orders A, B, C, D, E, F in that order; open the kitchen board |
| Expected UI | Real Kitchen Display board (`/branches/{id}/kitchen`), auto-refreshing, showing tickets with per-ticket action buttons |
| Expected API request | `GET /branches/{id}/kitchen-tickets` |
| Expected backend state | Tickets returned in fire order |
| Expected result | **PASS** — independently verified in the earlier run: 6 orders fired in sequence produced kitchen tickets in that exact same sequence, checked programmatically. |
| Evidence to capture | Ordered list of `orderId`s from the tickets response, compared against the fire sequence. |
| Potential failure conditions | None observed; re-confirm under Stage 6's larger burst as a regression check. |

---

### Stage 9 — Kitchen prepares food

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW (ticket level)**, **🟡 PARTIAL (item level)**

| Field | Detail |
|---|---|
| Actor | Kitchen staff |
| Starting state | Fired ticket, status `fired` |
| Action | Advance ticket: `fired → in_progress → ready` |
| Expected UI | "Mark in progress" / "Mark ticket ready" buttons on the KDS board — real and functional |
| Expected API request | `POST /kitchen-tickets/{id}/status` |
| Expected backend state | `KitchenTicket.status` transitions correctly; **but** `KitchenItem.status` on the same ticket's line items does **not** cascade — items can remain `queued` while their parent ticket reads `ready`. Confirmed live in the earlier run (three tickets simultaneously showed "Ready" with every item still "Queued"). |
| Expected result | **PASS** for ticket-level status. **KNOWN UX DEFECT** for item-level desync — record, do not treat as a new finding, it's already documented. |
| Evidence to capture | Side-by-side ticket-status vs. item-status DOM snapshot. |
| Potential failure conditions | None new expected. |

---

### Stage 10 — Bar prepares drinks

**Grade: ❌ NOT YET IMPLEMENTED / EXPECTED TO FAIL (as a distinct bar workflow)**

Mechanically identical to Stage 9 (same `KitchenTicket`/`KitchenItem` state machine, since Stage 7 confirmed there is no separate bar queue). There is no way to test "the bar prepares drinks" as its own workflow — a bartender using the KDS board today sees the exact same undifferentiated ticket list as the kitchen. Record this as the same gap as Stage 7, not a second independent bug.

---

### Stage 11 — Items are served

**Grade: ❌ NOT YET IMPLEMENTED / EXPECTED TO FAIL**

| Field | Detail |
|---|---|
| Actor | Waiter/kitchen staff |
| Starting state | Kitchen ticket `ready` |
| Action | Attempt to mark an order (or its items) as "served" |
| Expected backend state | **`OrderStatus.SERVED` is a defined domain state that no code path ever sets.** `Order` only exposes `mark_billed()`/`close()`, transitioning from `fired` directly to `billed`. `OrderItemLineStatus` similarly only exposes `fire()`/`void()` — there is no `serve()` method on the item entity either. The kitchen item's max reachable status is `ready`; the ticket's max is `ready` (a "served" ticket-status route exists per §10 UX note in admin-web's button label ("Mark ticket served") but confirm at test time whether this actually calls a real transition or is dead UI — flagged as a specific thing to verify, not assumed). |
| Expected DB state | No `orders.status = 'served'` row will ever be observed. |
| Expected result | **FAIL / NOT IMPLEMENTED.** This is an architecture-level gap (see PR review §H), not a UI oversight. |
| Evidence to capture | Attempt the transition via API directly (if a route exists) and record the actual error; if only a UI button exists, click it and record what it actually does (confirm whether it's silently a no-op, an error, or maps to a different real transition like `billed`). |
| Potential failure conditions | This is the single most consequential gap in the whole plan — it blocks Stage 12 (inventory deduction) entirely, since deduction was designed to hang off this milestone. |

---

### Stage 12 — Inventory should reflect consumption where the current implementation supports it

**Grade: ❌ NOT YET IMPLEMENTED / EXPECTED TO FAIL**

| Field | Detail |
|---|---|
| Actor | System (expected: automatic, on sale) |
| Starting state | Known opening stock of an ingredient (e.g., Chicken, 30kg) |
| Action | Sell and fully pay for 5 Chicken-containing dishes |
| Expected backend state | Recipe-linked ingredient quantities deducted from `inventory_items.quantity_on_hand` |
| Expected DB state | Reduced `quantity_on_hand` for Chicken |
| Expected result | **FAIL / NOT IMPLEMENTED — reconfirm, don't assume.** Already measured directly in the earlier run: Chicken stock was identical (30.0000kg) before and after billing/paying for 5 Chicken dishes. Root cause is Stage 11's dead "served" state — nothing ever fires the deduction. |
| Expected inventory behavior | Manual movements (adjustment, waste, purchase receipt) **do** work correctly and **are** testable now — this stage is specifically about *sale-driven* deduction, which does not exist. |
| Evidence to capture | `GET /inventory-items/{id}` before and after, byte-for-byte identical `quantityOnHand`. |
| Potential failure conditions | None — this is a confirmed gap, re-run only to catch regression or an unannounced fix. |

---

### Stage 13 — Customers add additional items

**Grade: 🟡 PARTIALLY IMPLEMENTED**

| Field | Detail |
|---|---|
| Actor | Waiter |
| Starting state | An order in `open` status (not yet fired) vs. an order already `fired` |
| Action | `POST /orders/{id}/items` on both |
| Expected backend state | On an `open` order: succeeds, real and tested. On a `fired` order: **rejected** — `409 INVALID_ORDER_STATUS_TRANSITION`, confirmed live in the earlier run ("Order cannot transition from 'fired' to 'item_added'"). There is also no endpoint anywhere to edit an existing line item's quantity or void a single line — confirmed by full OpenAPI route inspection. |
| Expected result | **PASS** for pre-fire additions. **FAIL / NOT IMPLEMENTED** for the realistic "the table wants one more round after the kitchen already has the ticket" case — this is the most common real-world request the system cannot handle today. |
| Evidence to capture | Both the successful pre-fire add and the rejected post-fire add, with the exact error body. |
| Potential failure conditions | None — confirmed behavior both ways. |

---

### Stage 14 — Bill is generated

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW**

| Field | Detail |
|---|---|
| Actor | Cashier/waiter |
| Starting state | Order `fired` (billing does not require `served`, since that state is unreachable — confirmed the system routes around its own dead state here) |
| Action | `POST /orders/{id}/bill` |
| Expected UI | Billing page renders subtotal/tax/adjustments correctly |
| Expected API request | `POST /orders/{id}/bill` |
| Expected backend state | `Bill` created, `status=open`, tax auto-applied from any active tenant tax |
| Expected result | **PASS** — tax auto-application, discount adjustments, and bill generation were all independently verified in the earlier run. |
| Evidence to capture | Bill response JSON; billing UI DOM snapshot. |
| Potential failure conditions | None expected. |

---

### Stage 15 — Partial payment is made

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW** *(status changed by this branch's latest commit — re-verify explicitly)*

| Field | Detail |
|---|---|
| Actor | Cashier |
| Starting state | Open bill, e.g. $23.76 due |
| Action | `POST /bills/{id}/payments` with `amount: 11.88` |
| Expected backend state | `Payment.status=settled`, `Bill.status=partially_paid`, `Bill.amount_paid=11.88` |
| Expected result | **PASS.** This was the site of a confirmed CRITICAL bug (`amountDue` never subtracted `amount_paid`, so the bill kept reporting the full original total after a partial payment, making the natural "pay the rest" flow impossible — it looked like an overpayment). **That bug was fixed in commit `7ef7553` on this branch** (`_bill_mapper.py`), verified with a new regression test plus the full unit/integration suite. This stage must be **re-verified live** as part of the simulation to confirm the fix holds under real conditions, not just unit-test conditions. |
| Evidence to capture | `GET /bills/{id}` immediately after the partial payment — confirm `amountDue` now equals the correct remainder, not the original total. |
| Potential failure conditions | If this regresses, it is the highest-priority finding the simulation could produce. |

---

### Stage 16 — Remaining balance is verified

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW** *(directly dependent on Stage 15's fix)*

| Field | Detail |
|---|---|
| Action | `GET /bills/{id}` after the partial payment |
| Expected result | `amountDue` = original total − amount already paid. Before the fix this stage would have failed outright; it is now expected to pass, pending live confirmation. |
| Evidence to capture | The exact JSON body, with the arithmetic shown explicitly in the report (subtotal + tax + adjustments − paid = due). |

---

### Stage 17 — Final payment is made

**Grade: ✅ IMPLEMENTED AND TESTABLE NOW**

| Field | Detail |
|---|---|
| Action | `POST /bills/{id}/payments` with `amount` = the (now-correct) remaining balance |
| Expected backend state | `Bill.status=closed`, and — because `fully_paid` triggers it — the underlying `Order.close()` runs too |
| Expected result | **PASS.** |
| Evidence to capture | Payment response; bill status; order status. |
| Potential failure conditions | An overpayment guard miscalculation would be the only realistic risk, and it does not share the buggy code path (confirmed: `record_payment.py` computes its own `amount_due` independently and was already correct before the fix — see PR review). |

---

### Stage 18 — Table/order is completed/closed

**Grade: 🟡 PARTIALLY IMPLEMENTED**

| Field | Detail |
|---|---|
| Action | Full payment completes; observe `Order.status` and `Table.status` |
| Expected backend state | `Order.status = closed` — **implemented**, confirmed. `Table.status` returning to `available` — **not implemented**; table status is a fully independent, manually-set field never touched by order lifecycle events. Confirmed live: all 13 tables read "available" throughout an entire simulated evening with heavy order/reservation activity against them (which also means an *occupied* table incorrectly shows as available before this stage, not just after). |
| Expected result | **PASS** for order closure. **FAIL / NOT IMPLEMENTED** for any floor-plan-style "this table is now free" signal — a manager watching table status gets no signal at all, in either direction. |
| Evidence to capture | Table status query before order-open, after order-fire, and after order-close — expect it to read "available" at all three points, which is itself the evidence of the gap. |
| Potential failure conditions | None — confirmed gap. |

---

### Stage 19 — Manager reviews the day's activity

**Grade: ❌ NOT YET IMPLEMENTED / EXPECTED TO FAIL**

| Field | Detail |
|---|---|
| Actor | Restaurant Manager |
| Starting state | End of the simulated day |
| Action | Log in as Manager, look for an end-of-day summary |
| Expected UI | Some dashboard or reporting page showing today's orders/revenue/payments/inventory/kitchen/reservations |
| Expected result | **FAIL / NOT IMPLEMENTED.** The main dashboard has no operational summary at all (confirmed: "Today's reservations" literally reads "Unavailable — select a branch," no revenue/order/kitchen widgets exist). There is no end-of-day report screen anywhere in the app. The only way to produce the numbers in §21 of the earlier simulation report was a direct database query — not something a real manager could do. |
| Evidence to capture | DOM snapshot of the dashboard as-is; explicit statement that no reporting surface exists. |
| Potential failure conditions | None — confirmed gap. |

---

## 6. Summary Matrix

| # | Stage | Grade |
|---|---|---|
| 1 | Guest scans QR (indoor) | 🟡 token resolution only |
| 2 | Guest orders via QR | ❌ no guest UI |
| 3 | Waiter order | ✅ |
| 4 | Outdoor order | ✅ |
| 5 | Rooftop order | ✅ |
| 6 | Concurrent order burst | ✅ |
| 7 | Kitchen/bar routing | ❌ no station separation |
| 8 | KDS FIFO queue | ✅ |
| 9 | Kitchen preparation (ticket) | ✅ / 🟡 item desync |
| 10 | Bar preparation | ❌ same gap as #7 |
| 11 | Items served | ❌ dead domain state |
| 12 | Inventory deduction on sale | ❌ not wired |
| 13 | Add items after fire | 🟡 pre-fire only |
| 14 | Bill generation | ✅ |
| 15 | Partial payment | ✅ (fixed this branch, re-verify) |
| 16 | Remaining balance | ✅ (fixed this branch, re-verify) |
| 17 | Final payment | ✅ |
| 18 | Table/order closure | 🟡 order yes, table no |
| 19 | Manager EOD review | ❌ no reporting UI |

**9 of 19 stages fully implemented, 5 partial, 5 not implemented.** None of the ❌/🟡 gradings are new discoveries — every one traces to a finding already documented in the earlier Sprint 7 simulation report. This plan's contribution is turning that into a repeatable, numbered procedure and re-confirming the one item that changed (Stages 15–16, following the `amountDue` fix).

## 7. Evidence Package Plan (for the eventual run)

When this plan is executed (only on explicit instruction — not yet), the run should produce:

1. **Screenshots at every stage** — confirm capture works *before* starting (§4.6); if it fails mid-run, stop and get explicit sign-off on a substitute evidence method before continuing, exactly as was necessary last time. Do not silently switch evidence types.
2. **API evidence** — full request/response JSON for every state-changing call, plus the specific `GET` calls listed per stage above as "evidence to capture."
3. **Database/state evidence** — direct queries for the few facts no API surfaces today (table status over time, inventory quantity-on-hand before/after, kitchen ticket `station` values).
4. **Test results** — if any stage's expected behavior is re-verified against the automated test suite (e.g., Stage 15/16's regression test), reference the specific test file/line, not just a pass/fail claim.
5. **Final PDF** — same structure as the prior report (title page, numbered sections, one per stage, findings appendix), explicitly noting which findings are *new* versus *already known and unchanged since the last run*.

## 8. Explicitly Out of Scope for This Document

- No code was written or modified to produce this plan.
- No simulation was executed.
- No new UI, endpoint, or database change was implemented.
- This document does not authorize starting the next development sprint.
