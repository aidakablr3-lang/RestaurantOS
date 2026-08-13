# RestaurantOS User Manual

**Version:** 1.0 (Pilot Edition)
**Date:** 2026-08-12
**Prepared for:** Prashanth AI

This manual describes only functionality that exists and has been verified in the current RestaurantOS system as of this date. It does not describe planned or future functionality. Where a limitation exists, it is stated plainly rather than hidden.

---

## Table of Contents

1. About RestaurantOS
2. Getting Started
3. User Roles
4. Restaurant & Branch Management
5. Table Management
6. QR Codes
7. Menu Management
8. Taking Orders
9. Kitchen & Bar Workflow
10. KDS / Queue
11. Billing
12. Payments
13. Table Closing
14. End-of-Day Reporting
15. Inventory
16. RBAC & Security
17. Common Daily Operating Procedure
18. Troubleshooting
19. Important Business Rules (Quick Reference)
20. Quick Reference Cards
21. Known Limitations

---

## 1. About RestaurantOS

RestaurantOS is a back-office and point-of-sale system for a single restaurant, bar, or hotel food & beverage operation. It covers the full flow from a guest placing an order through to the bill being paid and the day being reconciled.

**Who uses it:** the restaurant/branch manager, waiters, bartenders, kitchen staff, and an inventory manager, each with a different login and a different set of screens and actions available to them.

**Main workflow:**

```
Customer
  -> QR order (guest, self-service) OR Waiter order (staff-entered)
    -> Kitchen ticket / Bar ticket
      -> Preparation (Fired -> In Progress -> Ready -> Served)
        -> Bill generated
          -> Payment (partial and/or final)
            -> Table automatically becomes Available
              -> End-of-Day Reporting
```

Every step above exists in the current system and has been verified against a real, running deployment.

---

## 2. Getting Started

### Login

Staff log in with an email and password at the application's login page. There is no self-service sign-up for staff accounts — accounts are created by whoever administers the tenant.

`[SCREENSHOT — Login page: email field, password field, "Log In" button, RestaurantOS logo]`

### Dashboard

After login, staff land on a dashboard showing an operational summary for their branch (open orders, tables at a glance, and similar at-a-glance figures) rather than a blank landing page.

`[SCREENSHOT — Dashboard: operational summary cards, branch selector, sidebar navigation]`

### Navigation

The left sidebar lists the sections available to the logged-in user — which sections appear depends entirely on that user's role (see §16, RBAC). A Kitchen Staff login, for example, will not see a "Suppliers" or "Menu Editing" link, because that user has no permission to use those screens.

### Branch selection

Most screens (Tables, Orders, Kitchen, Billing, Inventory) are scoped to one branch at a time. If a user has access to more than one branch, a branch selector is available; most pilot deployments will have exactly one branch, so this will not usually come up.

### Permissions

What a logged-in user can see and do is enforced by the backend server, not just hidden in the interface. A button being visible does not by itself guarantee the action will succeed — but a button that would fail is, wherever the interface has been built out for that screen, hidden or disabled for a role that lacks the permission. See §16.

---

## 3. User Roles

Every action in RestaurantOS is gated by a real, server-enforced permission check — not just an interface convention. The roles below are the ones a pilot venue is expected to use. Two additional roles (**Cashier** and **Accountant**) exist in the system but are not covered in day-to-day detail here since they are not part of this pilot's core staffing plan; ask your administrator if your venue needs them.

### Owner / Admin (**Tenant Owner**)
- **Can see:** everything — every branch, every screen.
- **Can do:** everything — create/edit restaurants and branches, manage the menu, manage tables, take and manage orders, manage kitchen tickets, generate bills and take payment, manage inventory and purchasing, view all financial reports, and grant or revoke other users' roles.
- **Cannot do:** nothing is withheld from this role.
- **Typical responsibility:** overall business setup, staff account/role administration, and full oversight. In most hotel pilots this is used sparingly, by whoever is accountable for the whole deployment.

### Manager (**Restaurant Manager** / **Branch Manager**)
Two manager roles exist. **Restaurant Manager** covers every branch of a restaurant; **Branch Manager** is scoped to one specific branch. A single-branch hotel pilot will typically use **Branch Manager** for the on-site manager.
- **Can see:** branch details, tables, the menu (Branch Manager: read-only; Restaurant Manager: can also edit), reservations, orders, kitchen tickets, billing, inventory, purchasing, and reports.
- **Can do:** manage tables and their status, manage reservations, create/manage orders, manage kitchen tickets, generate bills and take payment, manage inventory and purchasing, view reports. Restaurant Manager can additionally edit the menu and branch settings.
- **Cannot do:** grant or revoke staff roles (Tenant Owner only).
- **Typical daily responsibility:** oversee the floor, step in on billing or table issues, review the end-of-day report, and make sure staff are following the table/order procedures in §17.

### Waiter
- **Can see:** tables, the menu, reservations, and orders.
- **Can do:** read tables and the menu, manage reservations, create and manage orders (add items, fire to the kitchen).
- **Cannot do:** generate or view bills, take payment, or touch inventory/purchasing. (A separate **Cashier** role exists for billing/payment duty if your venue splits those responsibilities from table service.)
- **Typical daily responsibility:** seat guests, take orders (or monitor guest QR orders on their tables), fire orders to the kitchen, and hand off to whoever holds billing responsibility once the meal is done.

### Bartender
- **Can see:** the menu, and kitchen/bar tickets.
- **Can do:** read the menu, read and update kitchen tickets (there is currently no separate bar-only ticket queue — bartenders use the same kitchen-ticket screen kitchen staff use, filtered to drink items by the ticket's own station field where the system routes items to a "bar" station).
- **Cannot do:** create orders, manage tables, or touch billing/inventory.
- **Typical daily responsibility:** work the ticket queue for drink items — mark them In Progress, Ready, and Served as they're prepared and handed off.

### Kitchen Staff
- **Can see:** the menu, and kitchen/bar tickets.
- **Can do:** read the menu (including availability/86'd-item status), read and update kitchen tickets.
- **Cannot do:** create orders, manage tables, or touch billing/inventory.
- **Typical daily responsibility:** work the kitchen ticket queue — Fired to In Progress to Ready to Served — for every food item.

### Inventory Manager
- **Can see:** inventory categories, inventory items and their stock levels, recipes, and purchasing (suppliers, purchase orders).
- **Can do:** manage stock levels (record adjustments, waste, transfers), define/revise recipes, manage suppliers and purchase orders.
- **Cannot do:** take orders, access the POS/kitchen workflow, or access billing.
- **Typical daily responsibility:** keep stock counts current, record deliveries via purchase orders and goods receipts, and manage recipes for menu items that need one.

**Why permissions matter in practice:** if a screen or button seems to be missing, the most likely explanation is that the logged-in role genuinely does not have that permission — this is enforced by the server, not a bug to work around. See §18 Troubleshooting.

---

## 4. Restaurant & Branch Management

- **Restaurant:** the top-level business entity (e.g., "Demo Rooftop Bar & Restaurant"). A restaurant can have one or more branches.
- **Branch:** one physical location (e.g., "Main Branch"). Tables, the live menu, orders, billing, and inventory are all scoped to a branch.
- **Branch status:** branches have an active/inactive-style status; an inactive branch is not available for day-to-day operations.
- **Operating hours:** each branch can have its weekly operating hours configured.
- **Branch management:** editing branch details (name, address, operating hours) is available to Restaurant Manager and Tenant Owner.

Only the branch-management functionality that actually exists in the current admin UI is described here — there is no separate "discontinued" state beyond active/inactive for a branch in the current system.

`[SCREENSHOT — Branch details page: name, address, operating hours, status]`

---

## 5. Table Management

### Table zones

Tables are organized into zones (dining areas) — for example Indoor, Outdoor, and Rooftop for a typical venue. Each zone contains a set of numbered tables (e.g., I1, I2, I3 for Indoor).

`[SCREENSHOT — Table zones/floor plan view, grouped by zone, each table showing its current status]`

### Table statuses

A table's status is one of: **Available**, **Occupied** (others may exist for administrative use, such as manually marking a table for cleaning — use these only when the situation genuinely calls for it, not as a substitute for the normal payment-driven release described below).

### Verified table lifecycle

This exact sequence has been verified against the real running system, repeatedly, including a dedicated critical-path test:

```
Available
  -> an order is created on the table -> Occupied
    -> a partial payment is made       -> still Occupied
      -> the bill is fully settled     -> automatically Available
```

**The table release on full payment is automatic.** Staff do not need to, and should not, manually change a table's status back to Available after a normal, successful final payment — the system does this for you, in the same instant the payment is recorded. See §13.

### Table reuse

Once a table is back to Available, a brand-new order can be created on it immediately, and the exact same cycle repeats. This has been verified working correctly, including on the very same table used earlier in the day.

### Important — multiple orders on one table

**Current, verified limitation:** the system does not currently prevent staff (or a QR-ordering guest) from creating a *second, separate* order on a table that already has one open. If this happens, the two orders are billed completely independently — this does not cause any billing errors, but it does mean a guest could unintentionally end up with two separate bills for one sitting instead of one combined bill.

**How to operate safely until this is improved:**
- If a table already has an order and the guest wants **more of the same visit** (another round, an extra dish), **add items to the existing order** rather than starting a new one. Waiters can add items to an order that has already been sent to the kitchen.
- Only start a brand-new order on a table once the previous one has been fully billed and paid (table has returned to Available).
- If your venue genuinely needs to split one table's visit into multiple separate checks on purpose, talk to your manager first — this is not yet a guided, built-in workflow and needs to be handled carefully to avoid confusing the guest or the till.

---

## 6. QR Codes

QR codes let a guest order directly from their phone without waiter involvement, for tables where this is enabled.

- **What they are:** each table can have a unique QR code linked to it.
- **How guests scan them:** the guest scans the code with their phone camera, which opens a link.
- **How it resolves:** the link takes the guest straight to that specific table's ordering page — the system already knows which restaurant, branch, and table the guest is at; the guest does not need to enter this themselves.
- **Guest menu:** the guest sees the full live menu for that branch.
- **Guest cart:** the guest adds items to a cart, adjusting quantities before submitting.
- **Guest order submission:** once submitted, the order is created and automatically sent ("fired") straight to the kitchen/bar — there is no separate manual "fire" step for a guest order the way there is for a waiter-entered one.

**Guest functionality vs. staff functionality:** the guest-facing QR pages are deliberately minimal — menu, cart, and order status only. Guests cannot see other tables, other orders, pricing/cost data beyond the menu's own listed prices, or any staff/admin screen.

`[SCREENSHOT — Guest QR landing: resolved table/branch banner, "View Menu" prompt]`
`[SCREENSHOT — Guest menu: categories and items with prices]`
`[SCREENSHOT — Guest cart: selected items, quantities, running total, "Submit Order" button]`
`[SCREENSHOT — Guest order confirmation: item statuses ("In the kitchen"), order total]`

---

## 7. Menu Management

- **Menu categories:** items are grouped into categories (e.g., Food, Drinks).
- **Menu items:** each item has a name and a price.
- **Food / Drinks:** there is no hard-coded "food vs. drink" split in the data model itself — categorization is whatever categories your venue defines — but items can be routed to a kitchen or bar preparation station (see §9), which is what actually determines who sees a ticket for that item.
- **Availability:** an item can be marked unavailable (commonly called "86'd" in restaurant terminology) without deleting it, so it stops appearing as orderable while it's out of stock, and can be turned back on later.
- **Modifiers:** items can have modifier groups attached (e.g., size, spice level, add-ons) where configured.
- **Branch pricing / availability overrides:** a menu item's price or availability can be overridden for a specific branch, for restaurants that operate more than one branch with different pricing.

Menu editing is available to Restaurant Manager, Tenant Owner, and Inventory Manager (for recipe-linked purposes); Branch Manager, Waiter, Bartender, and Kitchen Staff have read-only access to the menu — enough to know what's available to sell, not to change it.

`[SCREENSHOT — Menu category list with item counts]`
`[SCREENSHOT — Menu item detail: name, price, category, availability toggle]`

---

## 8. Taking Orders

There are two distinct ways an order enters the system.

### A. Guest QR Order

```
Guest: Scan QR -> View menu -> Add food/drinks to cart -> Submit order
```
The order is created and fired to the kitchen/bar automatically on submission. No staff action is required to start preparation, though staff should still be watching the kitchen/bar queue (§9-10).

### B. Waiter Order

```
Waiter: Select table -> Add food/drinks -> Review order -> Fire order
```
A waiter-entered order is **not** automatically sent to the kitchen the moment an item is added — it stays editable until the waiter explicitly fires it. This gives the waiter a chance to confirm the full order with the guest before it goes to preparation.

**The difference that matters operationally:** a guest QR order skips the "review, then fire" step entirely (submission = firing); a waiter order requires the waiter to take that extra, deliberate "Fire" action. Waiters should always confirm the order with the guest before firing it, since items already sent to the kitchen may already be in preparation.

`[SCREENSHOT — Waiter order entry: table selector, menu item picker, running order, "Fire Order" button]`

---

## 9. Kitchen & Bar Workflow

Once an order is fired (by either path above), each item on it is routed to a preparation ticket:

```
Order -> Ticket -> Station (Kitchen or Bar)
```

Items configured to route to the kitchen produce a kitchen ticket; items configured to route to the bar produce a bar ticket. One order with both food and drinks correctly produces both a kitchen ticket and a bar ticket, not one mixed ticket.

Every ticket then moves through the same four states:

```
Fired -> In Progress -> Ready -> Served
```

- **Kitchen Staff** should mark a kitchen ticket **In Progress** the moment they start preparing it, **Ready** the moment it's ready to leave the pass, and **Served** once it has actually been delivered to the table.
- **Bartenders** should do the same for bar tickets.

Marking an item **Served** is what tells the rest of the system the guest has actually received that item — it is also the trigger point for automatic inventory deduction, where a recipe is configured (§15).

`[SCREENSHOT — Kitchen Display Screen (KDS): ticket cards showing item, table, status, with status-change controls]`

---

## 10. KDS / Queue

- **Ticket queue:** the Kitchen Display shows every open ticket for the branch.
- **Kitchen queue / Bar queue:** tickets are split by their station, so kitchen staff and bartenders each see only their own relevant tickets.
- **Ordering staff should process tickets in:** the order they appear in the queue, top to bottom, unless a manager directs otherwise for a specific reason (e.g., a delayed table).

**On FIFO (first-in-first-out) behavior — read this carefully:** in real, repeated testing, tickets have consistently appeared in the queue in the exact order they were created, both across the whole branch and within each station individually. This is a genuinely observed, repeatable pattern under the conditions tested. However, **the system's own architecture documentation does not make a formal, written guarantee of strict first-in-first-out ordering** under all possible conditions (for example, very high concurrent load has not been tested to the same depth as normal service volume). Staff should treat the queue order as a reliable guide for normal service, not as an unbreakable promise — if something looks visibly out of order, use judgment and check with a manager rather than assuming the software is wrong or that it can never happen.

---

## 11. Billing

A bill is generated from a fired order once its items are ready to be paid for.

- **Subtotal:** the sum of the order's item prices (quantity x unit price).
- **Tax:** calculated automatically from the branch's configured tax rate(s) and added to the subtotal.
- **Total / Amount Due:** subtotal + tax, minus any adjustments (discounts), minus whatever has already been paid.
- **Amount Paid:** the running total of payments recorded against the bill so far.
- **Partial payment:** a payment for less than the full amount due is accepted; the bill stays open, and Amount Due reflects the remainder.
- **Full payment:** a payment that exactly covers the remaining Amount Due closes the bill.
- **Overpayment protection:** the system will not accept a payment larger than the current Amount Due — it is rejected with a clear error, and nothing about the bill or the table changes as a result of a rejected attempt. Re-enter the correct amount and try again.

`[SCREENSHOT — Bill detail: subtotal, tax, adjustments, amount paid, amount due, payment history]`

> **IMPORTANT BUSINESS RULE — Tips are not part of the RestaurantOS bill.**
> RestaurantOS v1 does **not** include a tip field anywhere in the billing or payment workflow. The amount a customer owes through RestaurantOS is exactly the food/drink subtotal plus tax — nothing else.
>
> If a guest wants to tip a waiter or bartender directly:
> - **Cash** can be handed to the server directly.
> - **UPI or another direct payment method** can be arranged directly between the guest and the server.
>
> **Do not attempt to add a tip amount into a RestaurantOS bill or payment — there is no field for it, and it should not be recorded in the system at all.** This is a deliberate business rule, not an oversight.

---

## 12. Payments

- **Amount to pay:** shown as the bill's current Amount Due; staff enter the amount actually being tendered for this payment (which may be less than, or exactly equal to, Amount Due — never more).
- **Partial payment:** accepted; leaves the bill (and the table) open.
- **Final payment:** the payment that brings Amount Paid up to exactly Amount Due.
- **What happens on full settlement (verified, automatic, in one step):**

```
Final payment recorded
  -> Bill closes
    -> Order closes
      -> Table automatically becomes Available
```

No separate "close bill," "close order," or "release table" action is needed or should be taken manually after a normal final payment — doing so is unnecessary and risks conflicting with the automatic behavior. See §13.

**Refunds:** RestaurantOS v1 has **no refund workflow**. There is no refund button anywhere in the product because the feature has been deliberately removed from this version. If a genuine refund situation arises (a payment made in error, a dispute), it must be handled entirely outside RestaurantOS, through whatever process your venue and payment provider use for that — cash handled directly, or through your card/UPI provider's own dispute process. Do not tell a guest or a colleague to "use the refund button" — it does not exist.

**Payment failures:** if a payment attempt is rejected (for example, the overpayment protection above), the system tells you why in a clear message. RestaurantOS itself does not process card/UPI transactions — it only records that a payment of a given amount and tender type was taken. Whatever your venue's actual card/UPI terminal or payment provider is remains the system of record for whether that underlying transaction itself succeeded; RestaurantOS does not make any claim about that on your behalf.

---

## 13. Table Closing

**Normal case:** do nothing extra. Once the final payment is recorded (§12), the table becomes Available automatically. This has been verified repeatedly, including the specific scenario of a table that was first partially paid and then fully settled later.

**Do not manually change a table's status after a successful final payment.** The only time a manual table-status change is appropriate is a genuine administrative situation the automatic flow doesn't cover — for example, marking a table temporarily unavailable for cleaning or maintenance, or the disclosed multi-order workaround in §5. If you find yourself manually releasing a table right after a payment because it "didn't seem to go available," treat that as a red flag: check with your manager before assuming this is normal, since a normal payment should have handled it by itself (see §18 Troubleshooting — "Table does not release").

---

## 14. End-of-Day Reporting

The end-of-day (EOD) report, run for a given date, shows:

- **Order count** and **voided order count**
- **Items sold count**
- **Gross sales amount** and **voided sales amount**
- **Total collected amount** (what was actually paid, across every tender type)
- **Total tips amount**
- **Total refunded amount**
- **Net collected amount**
- **Tender breakdown** (how much was collected by cash, card, etc., and how many payments of each)
- **Top items** sold that day

`[SCREENSHOT — End-of-day report: summary figures, tender breakdown table, top items list]`

> **IMPORTANT — read the Total Tips and Total Refunded lines correctly.**
> Given the business rules in §11-12, the EOD report's **Total Tips Amount will always read 0**, and **Total Refunded Amount will always read 0**. This is correct, expected behavior — it is not a bug, and it does not mean guests never tip in cash; it means RestaurantOS specifically does not track tips given directly to staff, by design. Do not interpret a 0 in either field as "no one tipped today" when reporting to ownership — it means "RestaurantOS does not record this category," full stop.

Independently recomputing the reported totals from the underlying bills (subtotal + tax per order) has been verified, in testing, to match the report's own totals exactly.

---

## 15. Inventory

**What currently works:** an Inventory Manager can create inventory categories and items, record stock movements (adjustments, waste, transfers — each requiring a reason and an approving user for an adjustment), and view current stock-on-hand for each item. Recipes can be defined for a menu item, linking it to the inventory ingredients it consumes and in what quantity.

**Automatic deduction — read this carefully:** when a menu item **has a recipe configured**, and one of its order items is marked **Served** (§9), the system automatically deducts the recipe's ingredient quantities from stock-on-hand. This has been built and is present in the system.

**However:** if a menu item has **no recipe configured**, marking it Served does **nothing** to stock levels — there is nothing to deduct. **Do not assume inventory is being tracked automatically for every menu item.** It only happens for items an Inventory Manager has explicitly given a recipe. If your venue wants automatic deduction for a given item, an Inventory Manager needs to build that item's recipe first; until then, treat that item's stock as something you must track manually (a manual stock adjustment, recorded the same way).

`[SCREENSHOT — Inventory item detail: stock on hand, reorder point, recent stock movements]`
`[SCREENSHOT — Recipe editor on a menu item: ingredients and quantities]`

---

## 16. RBAC & Security

RBAC stands for Role-Based Access Control. Every user is assigned one or more roles (§3), and every role has a fixed, specific list of permissions.

- **Why users see different screens:** the interface only shows a section if the logged-in user's role has at least read access to it.
- **Why some buttons may not appear:** the same principle — an action's button is hidden if the role can't perform it.
- **Backend authorization:** this is the important part — permissions are checked again on the server for every single action, not just hidden in the interface. Even if someone found a way to make a hidden button appear, the server would still refuse the action if the role doesn't have the permission. This has been directly, repeatedly verified: attempting an unauthorized action returns a clear "permission denied" error, not a silent failure and not an accidental success.
- **Branch-level access:** most roles are granted per branch — a Waiter granted at one branch cannot act on a different branch's tables/orders, even within the same restaurant, unless separately granted there too.

---

## 17. Common Daily Operating Procedure

### Manager
1. Log in.
2. Confirm the correct branch is selected.
3. Check the Tables view for anything unexpected (a table still Occupied from the day before, for example).
4. Spot-check the menu for correct availability (anything 86'd that shouldn't be, or vice versa).
5. Confirm staff are logged in under their own accounts, not shared logins.
6. Monitor orders throughout service.
7. Monitor the kitchen/bar queue for anything stuck.
8. Monitor billing — watch for any bill that's been open unusually long.
9. Run and review the End-of-Day report at close.

### Waiter
1. Seat the customer, or direct them to the table's QR code if self-ordering.
2. Take the order, or monitor the guest's QR order as it comes in.
3. Fire the order once confirmed with the guest.
4. Follow it through preparation via the kitchen/bar queue status.
5. Present the bill once the meal is complete.
6. Record the payment (hand off to a Cashier if your venue splits this duty).
7. Confirm the table returns to Available automatically — do not release it manually.

### Kitchen Staff
1. Open the Kitchen Display.
2. Process tickets in queue order.
3. Mark In Progress when starting.
4. Mark Ready when done.
5. Mark Served once actually handed off (this may be done by kitchen staff or waitstaff, depending on your venue's own handoff convention — RestaurantOS doesn't mandate which).

### Bartender
Same four steps as Kitchen Staff, applied to bar tickets.

### Inventory Manager
1. Review current stock levels.
2. Record any deliveries as a purchase-order goods receipt (adds stock).
3. Record any waste/breakage/adjustment as a stock movement, with a reason.
4. Keep recipes current for any item you want auto-deducted (§15).
5. Do not attempt to manually "simulate" a sale-driven deduction by recording an adjustment that mimics one — the report will not distinguish it from a real correction, and it defeats the purpose of tracking real vs. recipe-driven usage separately.

---

## 18. Troubleshooting

| Symptom | Likely cause | What to do | Escalate to manager if... |
|---|---|---|---|
| Cannot log in | Wrong email/password, or account not yet created | Double-check credentials; confirm the account exists | Credentials are confirmed correct and it still fails |
| No access to a screen | Your role doesn't have that permission (§16) | This is very likely correct/expected behavior — confirm with your manager what your role should have | You believe your role should have access and it doesn't |
| Table appears Occupied but shouldn't be | A previous order/bill on that table was never fully settled, or (rarely) a stale-process/environment issue | Check if there's an open bill for that table before assuming it's wrong | The table has no open order/bill you can find, yet stays Occupied |
| Order not visible | Wrong branch selected, or the order was created on a different table/branch than expected | Confirm branch selection; search by table | Still missing after confirming branch and table |
| Ticket not visible in KDS | The order may not have been fired yet, or you're viewing the wrong station's queue | Confirm the order was fired; check both kitchen and bar queues | The order shows as fired but no ticket appears anywhere |
| Payment rejected | Likely an overpayment attempt (amount entered exceeds Amount Due), or a network/connectivity issue | Re-check the exact Amount Due and re-enter the correct amount | Correct amount still gets rejected |
| Overpayment error | You entered more than Amount Due — this is the system working correctly, not a bug | Re-enter the exact Amount Due | N/A — this is expected behavior |
| Table does not release after full payment | Should be automatic (§13) — if it isn't, this may indicate a real issue with the running system | Do not manually release it as a first response; note the exact order/bill/table and time | Immediately — this is a known-critical class of issue |
| QR doesn't resolve | The QR code may be for a different branch/table than intended, or may have been regenerated/revoked | Confirm you're scanning the current, correct code for that table | The correct code still doesn't resolve |
| Menu item unavailable | The item has been intentionally marked unavailable (86'd), or a branch-specific override hides it | Check with kitchen/management before assuming it's an error | You believe it should be available and it's blocking service |
| Wrong branch showing | Branch selector set incorrectly, or your account isn't granted at the branch you expected | Re-select the correct branch | Your account isn't granted at the branch you need |
| Server/backend unavailable | The application server may be down or restarting | Wait briefly and retry; do not attempt to work around it with pen-and-paper billing without telling a manager | Still unavailable after a few minutes |

---

## 19. Important Business Rules — Quick Reference

- Customer pays only the restaurant bill (food/drink subtotal + tax).
- Tips are outside RestaurantOS — cash or direct UPI to the server, never entered into the system.
- There is no RestaurantOS refund workflow — handle refunds entirely outside the system.
- Partial payment keeps the table Occupied.
- Final payment releases the table automatically — never release it manually as a normal step.
- Overpayment is rejected automatically — no state changes when it is.
- Kitchen and bar tickets follow the current queue behavior described in §10 — reliable in normal use, not a formally guaranteed promise under all conditions.
- Permissions are enforced by the server on every action, not just hidden in the interface.
- Automatic inventory deduction only happens for menu items with a configured recipe — not implemented for every item by default.
- The system currently allows more than one order to exist on the same table at once — follow the safe-operating guidance in §5 to avoid accidentally creating two bills for one visit.

---

## 20. Quick Reference Cards

### MANAGER — Daily Checklist
- [ ] Log in, confirm branch
- [ ] Check tables for anything left over from yesterday
- [ ] Check menu availability
- [ ] Confirm staff logins
- [ ] Monitor orders/kitchen/bar/billing through service
- [ ] Run and review End-of-Day report

### WAITER — Order & Payment Checklist
- [ ] Seat guest / point to QR code
- [ ] Take order or monitor QR order
- [ ] Confirm with guest, then Fire
- [ ] Track through preparation
- [ ] Present bill
- [ ] Record payment (or hand to Cashier)
- [ ] Confirm table auto-released — do not release manually

### KITCHEN — KDS Checklist
- [ ] Open Kitchen Display
- [ ] Work tickets in queue order
- [ ] Fired -> In Progress -> Ready -> Served, in order, no skipping

### BARTENDER — Bar Checklist
- [ ] Same as Kitchen checklist, for bar-station tickets

### INVENTORY MANAGER — Inventory Checklist
- [ ] Review stock levels
- [ ] Record deliveries via goods receipt
- [ ] Record waste/adjustments with a reason
- [ ] Keep recipes current for auto-deduction items
- [ ] Never fabricate a "sale deduction" manually

---

## 21. Known Limitations

Verified directly against the current code and the most recent full-restaurant-day simulation (Run 4) at the time of writing:

1. **Multiple concurrent orders can exist on one table.** The system does not currently prevent a second, unrelated order from being created on a table that already has one open. See §5 for the safe-operating workaround. This does not corrupt billing, but it can produce two separate bills for one visit if not handled carefully.
2. **Automatic inventory deduction only works for menu items with a configured recipe.** It is built and functions correctly where a recipe exists, but is not automatic for items without one. See §15.
3. **No formally guaranteed FIFO ordering promise.** Ticket ordering has been reliably observed to follow creation order in real testing, but this is not a documented, absolute architectural guarantee under every possible condition. See §10.
4. **No refund workflow.** Deliberately removed in this version. See §12.
5. **No tip field.** Deliberately excluded from this version. See §11.
6. **Cash Drawer status is not persisted across a page reload** — the "currently open drawer" for a branch is tracked only in the browser session that opened it, not fetched fresh from the server. If your venue uses the Cash Drawer feature, be aware a page refresh can lose track of which drawer is open (the drawer itself is not affected — only the interface's memory of it).

This manual will be updated as these items are addressed in future versions.
