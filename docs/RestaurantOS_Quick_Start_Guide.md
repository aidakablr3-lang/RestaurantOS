# RestaurantOS Quick Start Guide

**Version:** 1.0 (Pilot Edition) — **Date:** 2026-08-12

A short, daily-use operational guide. For full detail, background, and troubleshooting, see `RestaurantOS_User_Manual.md`/`.pdf`.

---

## Login
Go to the login page, enter your email and password. What you see next depends on your role — this is normal.

## Tables
Tables live in zones (e.g., Indoor, Outdoor, Rooftop). Status is **Available** or **Occupied**. A table becomes Occupied the moment an order is created on it, and becomes Available **automatically** the moment its bill is fully paid — never change this manually after a normal payment.

**One open order per table at a time.** If a table already has an order, add items to it rather than starting a second one — the system currently allows a second order, but it will bill separately and can confuse the guest.

## QR Orders (guest, self-service)
Guest scans the table's QR code -> sees the menu -> adds items to cart -> submits. This automatically fires straight to the kitchen/bar — no staff action needed to start it, but keep an eye on the queue.

## Waiter Orders
Select the table -> add items -> review with the guest -> **Fire**. Unlike a QR order, a waiter order does not go to the kitchen until you explicitly fire it — make sure you actually press Fire once you're done.

## Kitchen
Open the Kitchen Display. Work tickets top to bottom: **Fired -> In Progress -> Ready -> Served.** Don't skip a step. Food items land here; drinks land on the Bar queue instead.

## Bar
Same as Kitchen, for drink tickets: **Fired -> In Progress -> Ready -> Served.**

## Billing
Generate the bill once the order is ready to be paid. It shows Subtotal, Tax, Amount Paid, and Amount Due. **There is no tip field — do not try to add one.** If a guest wants to tip, that's handled directly with the server (cash or UPI), outside RestaurantOS entirely.

## Payment
Enter the amount being paid — never more than Amount Due (the system will reject an overpayment and nothing changes when it does). A partial payment is fine; the bill and table both stay open. The payment that brings Amount Paid to exactly Amount Due closes the bill.

**There is no refund button.** RestaurantOS v1 doesn't have one. A real refund is handled entirely outside the system.

## Table Release
This is automatic. The instant a bill is fully paid: the bill closes, the order closes, and the table goes back to Available — **by itself.** Don't manually mark it available. If it doesn't happen on its own, stop and tell your manager immediately rather than fixing it by hand.

## End-of-Day
Run the End-of-Day report at close. It shows order count, gross sales, amount collected, tax, tender breakdown, and top items. **Tips and Refunds will always show 0** — that's correct, since RestaurantOS doesn't track either one, not because nobody tipped today.

---

### One-line reminders
- Add to the existing order — don't start a second one on an occupied table.
- Fire waiter orders explicitly; QR orders fire themselves.
- No tips, no refunds, in the system — ever.
- Never manually release a table after a normal payment.
- Inventory only auto-updates for menu items with a recipe configured — ask your Inventory Manager which ones those are.
