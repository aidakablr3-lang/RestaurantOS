# RestaurantOS — Enterprise Data Architecture Review Board Report

**Document type:** Formal Data Architecture Production-Readiness Review
**Reviewed artifact:** [RestaurantOS Enterprise Data Architecture (Sprint 2)](RestaurantOS_Data_Architecture.md)
**Review posture:** Adversarial, from the perspective of Principal Database Engineers at PostgreSQL, Stripe, Shopify, Amazon, Google, and Microsoft. This board defends nothing it did not verify itself.
**Verdict up front:** The data architecture demonstrates genuinely strong foundational thinking — the multi-tenancy/RLS fix, the HLC/ULID sync model, and the outbox/inbox event backbone are all sound. But this review finds **9 Critical and 8 High-severity gaps**, several of which mean specific, named Blueprint features (liquor variance reporting, bar tabs, discount workflows, per-rate tax reporting) **cannot actually be implemented on the schema as written**, and one — the absence of any tenant-level restore capability in a shared-schema multi-tenant design — is a material operational risk at the platform's stated scale. This is not a 9.5. It is not close.

---

## 1. Domain Model

**Missing entities — not stylistic gaps, but entities the Blueprint's own features cannot function without:**

- **Tip / Gratuity has no representation anywhere in the schema.** Zero column, zero entity. Blueprint's Payroll Ready module explicitly requires "tip pooling/distribution" (Blueprint §6). A restaurant POS with no tip data model is not a restaurant POS.
- **ServiceCharge** (automatic gratuity for large parties, banquets — universal in hospitality) — absent.
- **Discount/Promotion has no entity.** Order carries only `subtotal_amount`, `tax_amount`, `total_amount` — no `discount_amount`, no discount reason, no linkage to the discount-approval workflow that BR-14 (cashier discount requiring manager approval above a threshold) explicitly requires. The business rule exists in prose across three prior documents; it has no column to attach to.
- **A pending-approval workflow entity is missing.** `AuditEvent` records that an approval *happened*; nothing records that one is *awaited* (Blueprint M2: a manager approves a void/refund/discount remotely, from their phone, potentially minutes after the request). Without a first-class `ApprovalRequest` (status: pending/approved/denied, requested_by, approved_by, expires_at), this entire manager-mobile-approval workflow — a named Must-Have — has no backing data structure.
- **CurrencyExchangeRate is absent.** `Currency` is pure reference data with no rate table. At "100+ branches per tenant," a chain operating across borders cannot produce a consolidated multi-currency P&L without one.
- **Branch-level menu/price override is architecturally impossible as modeled.** `MenuCategory`/`MenuItem` belong to `Restaurant`, with one flat `price_amount` per item. The Product Blueprint's Menu Management module explicitly promises "per-branch price overrides" and "scheduled menus (breakfast/lunch/happy hour)." There is no override table and no time-scheduling entity. Every branch under a Restaurant is forced to sell at an identical price with no path to differentiate — a direct, unresolved contradiction between this document and the Blueprint it claims to implement.
- **OrderTaxLine (per-rate tax breakdown) is missing.** `orders.tax_amount` is one aggregate number. The Blueprint's Tax/GST Report requires "taxable sales and tax collected **by rate**" — a single column cannot decompose which portion of tax came from which `Tax` rate (relevant the moment an order mixes food and alcohol taxed differently). This directly breaks a named Must-Have report.
- **Recipe cost is never snapshotted at sale time.** `order_items.unit_price_amount` snapshots the *selling* price correctly, but nothing snapshots the *recipe cost* at that moment. Recipes are versioned (Part 2 §5.7) specifically to preserve historical cost accuracy — but with no cost snapshot on `OrderItem`, a historical Food Cost % report (a headline Blueprint KPI) can only ever use *today's* ingredient costs against *yesterday's* sales, silently corrupting every historical margin report the moment a single ingredient price changes.

**Wrong/ambiguous relationships:**

- **`LiquorBottle` is cataloged but never wired into `StockMovement`.** Part 1 introduces it as "a specific trackable instance" of a liquor `InventoryItem," but Part 2's `stock_movements` spec has only `inventory_item_id` — no `liquor_bottle_id`. The entire liquor pour-cost variance capability (Blueprint B4, explicitly called out as a competitive differentiator against generalist POS platforms) **cannot be built on this schema** — there is no way to attribute a fractional pour deduction to a specific opened bottle.
- **`ModifierGroup`'s relationship to `MenuItem` is self-contradictory.** Part 1's catalogue says it "belongs to MenuItem," then in the same sentence says "or shared across items — modeled as its own entity referenced by a join." Part 2 never resolves this with an actual join table. As written, an engineer cannot tell whether `ModifierGroup` needs a foreign key or a many-to-many association table.
- **The `Order`↔`Bill` aggregate boundary cannot represent a running tab.** The model is strictly `Order ||--o{ Bill` — one order, optionally split into several bills. Blueprint B3 requires the opposite direction to also exist: a bartender's tab accumulating *multiple separate orders* over an evening, settled with *one* bill. The current schema has no path for one `Bill` to close out several `Order`s. This is a real aggregate-design error, not a missing nice-to-have — it blocks a named workflow.
- **No support for a non-catalog, ad-hoc-priced `OrderItem`.** `order_items.menu_item_id` is `NOT NULL`. Every real-world POS eventually needs a cashier to ring up a manually-priced "misc" item; this schema structurally cannot.

**Possibly-redundant entity worth collapsing:** `StockAdjustment` largely duplicates `StockMovement` with `movement_type='adjustment'` plus a reason/approver — this could plausibly be flattened into `StockMovement` itself (adding `reason_code`, `approved_by_user_id` columns), removing a table and a join for no loss of information. Worth a design decision, not a blocker.

---

## 2. Normalization

- **1NF:** Compliant; the one JSONB usage (`order_items.modifiers_snapshot`) is a defensible, explicitly-scoped exception (frozen, never queried relationally), not a violation.
- **3NF violation (intentional, documented, but under-guarded):** `inventory_items.quantity_on_hand` is a value functionally determined by data in a *different* table (`stock_movements`), maintained by a trigger. This is a reasonable, common, performance-motivated denormalization (ADR-D4) — but the design never addresses the operational reality that **bulk data-loading paths (migrations, corrective scripts, replication catch-up) commonly disable triggers for performance**, at which point `quantity_on_hand` silently goes stale with zero detection mechanism. A derived value this central to a hard business rule (BR-8, no overselling) needs an independent reconciliation/verification job, which does not exist anywhere in this document.
- **BCNF / key-integrity violation on join tables — a real, concrete bug:** `UserRole` and `RolePermission` follow the universal `ULIDPrimaryKeyMixin` convention, giving each a surrogate ULID primary key **with no accompanying composite unique constraint** ever specified on `(user_id, role_id, branch_id)` or `(role_id, permission_id)`. As documented, nothing stops the same role being assigned to the same user for the same branch twice, or a permission being granted to a role twice. Applying a universal "every table gets a ULID PK" convention to pure association tables — where the natural composite key already is the correct primary key — was a mechanical application of a mixin without considering the table's actual shape. This is a genuine design defect, not a stylistic quibble: it silently permits duplicate/ambiguous authorization state in the identity model.

---

## 3. Relationships

- **Cascade/delete rules are absent from the entire document.** Not one `ON DELETE` behavior is specified for any of the dozens of foreign keys detailed in Part 2. This is not a minor omission — it directly **contradicts a workflow this same document requires**: Part 1 §4.6 mandates a scheduled purge job physically deleting an offboarded tenant's rows. Without explicit, deliberately-ordered `ON DELETE CASCADE`/`RESTRICT` policy per relationship, that purge job as specified would hit default Postgres `NO ACTION` behavior and fail outright on the first FK-referenced row it tries to remove, or require an undocumented, error-prone, hand-built deletion order maintained outside the schema.
- **Optional vs. required relationships are mostly sound** (`Order.customer_id`, `Order.table_id` correctly nullable for guest/takeaway flows) — this is a genuine strength of the design and the review credits it.
- **Many-to-many modeling is inconsistent.** Some many-to-many relationships (`RolePermission`, `UserRole`) are explicit join tables; `ModifierGroup`↔`MenuItem` is left unresolved (§1). This inconsistency suggests the pattern wasn't applied systematically across the catalogue.

---

## 4. Keys

- **`CHAR(26)` for ULID storage is a PostgreSQL anti-pattern.** A PostgreSQL-specialist reviewer flags this immediately: Postgres's `CHAR(n)` has **no storage advantage** over `varchar`/`text` (both use the same variable-length internal representation once padding is accounted for) and introduces surprising comparison/trimming semantics around trailing whitespace that `text` does not have. ADR-D1 chose the right *logical* format (a 26-character Crockford Base32 string) but the wrong *physical* Postgres type. **Correct choice: `TEXT` with a `CHECK (length(id) = 26)` constraint**, which gets the same fixed-length guarantee without any of `CHAR(n)`'s footguns. This affects every one of the 60 tables and should be fixed now, before a single table is created, since it is a mechanical, low-risk, high-value fix that becomes materially more disruptive after data exists.
- **Composite/natural key gap on join tables** — restated from §2: `UserRole`/`RolePermission` need their natural composite key enforced as either the actual primary key or, at minimum, an explicit unique constraint; a bare ULID surrogate with no uniqueness guard is a defect.
- **ULID-as-PK insert hot-spotting is unaddressed.** ULIDs are time-sortable by design, which is excellent for BRIN indexes and range queries — but it also means every concurrent insert into a high-write table clusters at the physical "end" of the table/index, a well-known PostgreSQL scaling concern under very high concurrent write throughput (buffer contention on the trailing page). The design gets a partial pass because `InventoryItem`/`StockMovement`/`Order` are branch-scoped, naturally bounding per-branch concurrency to a small number of terminals — but this mitigating factor is never stated or verified in the document; it currently reads as an unrecognized risk rather than a deliberately-accepted, monitored trade-off.

---

## 5. Money

This is one of the two most consequential problem areas in the entire review. Tips, service charges, and discounts have **no representation at all** (§1) — for a commercial restaurant POS, this is not a gap in a secondary feature, it is a gap in the primary transaction record.

- **Exchange rates:** absent (§1) — blocks multi-currency consolidation for cross-border chains.
- **Rounding:** `NUMERIC(19,4)` is the right storage type (ADR-D2, credited), but the document never specifies **where in the calculation pipeline rounding is actually applied** — per line, per tax rate, or once at the bill total — nor which rounding mode (several jurisdictions mandate specific cash-rounding rules, e.g., rounding to the nearest 5 cents where 1-cent coins have been withdrawn). Two implementations following this document could legally produce different totals for the identical order.
- **Ledger readiness — a Stripe-caliber reviewer's central objection:** this schema has no unifying ledger abstraction. `Payment`, `Refund`, `Expense`, and `PurchaseOrder` are independent, disconnected single-entry facts. There is no mechanism that guarantees "the books balance" in any formal sense, and no path to producing a trial balance or general-ledger export for the Blueprint's own stated goal of Accounting integrations. This is architecturally acceptable **only** if explicitly deferred (as the roadmap's Phase 3+ accounting-integration timing would justify) — but it is never stated as a deferred decision; it reads as an oversight, not a scoped choice.
- **Historical accuracy** is undermined by the missing recipe-cost snapshot (§1) — selling price history is solid; cost history is not.

---

## 6. Inventory

- `LiquorBottle` disconnection from `StockMovement` (§1) — Critical, restated here as its own inventory-domain finding.
- **No unit-of-measure conversion table.** `RecipeIngredient.quantity` + a free-text `unit` column, with unit conversion explicitly waved off as "business logic out of scope" — but a `Recipe` costed in grams against an `InventoryItem` stocked in kilograms, with no conversion table, produces **silently wrong cost calculations**, not merely an inconvenience. This is a data-integrity gap, not a business-logic nicety.
- **No negative-inventory enforcement.** TAD v2.0's own Business Rule (BR-8: stock cannot go negative through normal sale deduction, with a per-branch configurable backorder tolerance) has **zero schema-level enforcement** — no `CHECK` constraint, no `allow_negative_stock` flag on `Branch`/`InventoryItem`. The rule exists only as prose across three documents and depends entirely on application code never having a bug. Given this system explicitly tolerates offline, concurrently-replayed writes (§8), an enforcement-free negative-inventory rule is a when-not-if failure.
- **Transfers are named as a `movement_type` enum value with no supporting structure.** A stock transfer between branches needs two linked `StockMovement` rows (debit at source, credit at destination); nothing pairs them, so reconciling "did every transfer's outbound leg have a matching inbound leg" is unauditable as designed.
- **No `SupplierReturn` and no rejected/returned-quantity tracking on `GoodsReceipt`.** A goods-received discrepancy is mentioned in the business-rules layer (BR-9) but has no matching data structure for the return-to-supplier side of that discrepancy.

---

## 7. Orders

- The `Order`/`Bill` aggregate-boundary defect (§1) is the dominant finding here — it blocks both split-tab-across-orders (bar tabs) and, symmetrically, merging two tables' separate orders into one bill, a workflow the Blueprint (W5) explicitly names.
- **Kitchen remake/re-fire scenario is undocumented.** `KitchenItem` as a layer separate from `OrderItem` is defensible specifically *because* an item can be remade (a new `KitchenItem` against the same `OrderItem`) — but this document never states that as the reason, leaving a future engineer to guess why the extra table exists at all.
- Offline-order handling (`origin_device_id`, `opened_at` as HLC-derived vs. `created_at` as server-insertion time) is genuinely well thought through — the review credits this explicitly as a strength.

---

## 8. Offline Synchronization — Stress Test Results

| Scenario | Result |
|---|---|
| **Two terminals edit the same open order concurrently** | **Fails to converge cleanly.** The Conflict Resolution Registry assigns `orders` wholesale to the `append_only` strategy, which is correct for the *new rows* two waiters add concurrently (fine) — but `orders.subtotal_amount` is a **stored, non-generated** column that application logic recomputes and pushes as items are added. Two devices independently recomputing and writing a new `subtotal_amount` for the same open order is a last-write-wins race the registry's coarse, per-aggregate-type strategy does not account for, because it treats "Order" as one monolithic aggregate when it actually mixes append-only children (`OrderItem`) with a racy mutable parent field. **Fix: make `subtotal_amount` a generated/derived value (summed from `OrderItem`s at read time or via the same trigger pattern as `quantity_on_hand`), never an independently-pushed stored value.** |
| **Network disconnect during payment** | **Partially addressed.** `Payment.status` lacks a distinct "attempted, outcome unknown" state — `authorized` implies a known-good result. A device that loses connectivity mid-authorization cannot represent "I don't yet know if this succeeded," risking either a false retry (double-charge risk, mitigated only by the idempotency key) or a false negative. Needs an explicit `pending_reconciliation` status. |
| **Inventory changed on two devices** | **Well handled** — commutative-delta replay is genuinely correct for this case. Compounded by the missing negative-inventory guard (§6): two devices both depleting the last unit, followed by a third stale-cached device selling once more, drives the ledger negative with nothing to stop it. |
| **Duplicate replay** | **Solid.** ULID-as-idempotency-key with `ON CONFLICT DO NOTHING` is correct and efficient. |
| **Clock drift** | **Solid in mechanism, unstated in limitation.** HLC correctly neutralizes clock drift for causally-related operations, but the document never states the corollary: for two devices that are *both* offline and never exchange any information before both syncing, HLC provides no true global ordering guarantee — resolution falls entirely to each aggregate's registered strategy. This is an acceptable, standard HLC limitation, but presenting it as fully solved without this caveat will mislead an implementing engineer. |
| **Out-of-order operations** | **Only half-designed.** Intra-batch reordering by HLC is specified; **inter-batch** ordering (batch 2 arrives and applies before a retried, delayed batch 1) is never addressed. This is a genuine, exploitable gap under exactly the adverse network conditions this feature exists to survive. |
| **Sync after several days offline** | Adequately addressed via bounded stream retention + full-snapshot fallback. |
| **Terminal replacement / lost device** | **A real, unaddressed gap.** No device-level revocation/deny-list independent of user-level session revocation exists. No mechanism flags "this device hasn't synced in N hours" as a staleness/loss signal. Most importantly: **a lost device's un-synced local operation log is simply gone** — every order rung up on it since its last successful sync is unrecoverable, with no design requirement (e.g., a maximum acceptable un-synced window, forcing more frequent incremental pushes) to bound that exposure. |

---

## 9. Event Architecture

- **Outbox dispatch ordering is not actually guaranteed by `ORDER BY created_at`.** Under concurrent transactions, Postgres MVCC visibility means a transaction that started earlier (and thus has an earlier `created_at`) can commit *after* a later-started transaction, becoming visible to the Relay Dispatcher's poll out of timestamp order. `ORDER BY created_at` on an outbox table does not, by itself, guarantee true commit-order dispatch under concurrency — this needs either a monotonic dispatch-ordering mechanism or an explicit, documented acceptance that consumers must be order-tolerant (which the Inbox/idempotency design mostly supports, but this was never stated as a deliberate trade-off).
- **No durable historical event log beyond the bounded Stream retention window.** A future consumer (a new analytics pipeline, added a year from now) cannot backfill against events older than the 24–72 hour retention window. This is consistent with — and reinforces — the already-acknowledged AI-readiness gap, but deserves restating specifically as an event-architecture limitation, not just an analytics one.
- Idempotency, retries, and the dead-letter design are genuinely solid — credited without reservation.

---

## 10. Multi-Tenancy

- The `SET LOCAL` fix for RLS/PgBouncer compatibility is **the single best piece of engineering in this entire document** — correct, precise, and exactly what a PostgreSQL specialist would demand. Full credit.
- **Tenant-level restore is entirely unaddressed — see §16, this review's most severe single finding.**
- **Tier-promotion policy (shared → dedicated) has no defined trigger.** Nothing specifies *when* a growing tenant is actually moved to dedicated infrastructure — by branch count? by write volume? manually, after a complaint? Without a defined threshold, a 100-branch tenant can remain on `shared` tier well past the point it becomes a noisy neighbor to everyone else on that shard.
- **Background-job fan-out at 10,000-tenant scale is unspecified.** A platform-wide per-tenant nightly job (e.g., report generation) looping over 10,000 tenants, each requiring its own `SET LOCAL`-scoped transaction, has real connection/transaction-overhead implications that are never modeled or bounded.

---

## 11. PostgreSQL

- `CHAR(26)` anti-pattern — restated from §4, the most broadly-applicable fix in this review.
- **No mention of extended statistics.** `tenant_id` and `branch_id` are highly correlated (a given `branch_id` implies exactly one `tenant_id`), yet every composite index leads with both. Without `CREATE STATISTICS` on these correlated pairs, the query planner's default per-column statistics can materially misestimate selectivity for the composite filters this entire schema is built around — a real, fixable, currently-unaddressed tuning gap.
- **HOT-update eligibility for the `quantity_on_hand` trigger path is never verified.** This column is updated at high frequency by design (§10.3 of the original document); whether any index inadvertently covers it (breaking Heap-Only-Tuple update optimization and increasing bloat/vacuum pressure) is never checked or stated as a constraint future migrations must preserve.
- **Write amplification is never quantified**, despite being explicitly in scope for this review: a single `Order` insert cascades into `OrderItem` inserts, an `InventoryItem` trigger-driven update, an `outbox_events` insert, and multiple index maintenance operations across `orders`' three indexes — a real, multi-table write cost per transaction that was never modeled or budgeted.

---

## 12. SQLAlchemy

- `lazy="raise"`-by-default and the tenant-scoped base repository are sound, credited patterns.
- **Partitioned-table interaction with the ORM is never addressed.** SQLAlchemy relationships and FK constraints against a declaratively-partitioned parent table have real, well-known rough edges (a child table's FK must reference the *partition key* combination, not just the logical PK) that this document's heavy reliance on partitioning (§10.4 of the source document) never acknowledges at the ORM-mapping level.
- **Ambiguous repository base-class scope.** It's unclear whether the single tenant-scoped base repository correctly excludes platform-level tables (`tenants`, `permissions`, `currencies`) or whether a second, unscoped base class exists — a real place for an engineer to either wrongly tenant-filter platform data (breaking it) or forget to scope a table that should be tenant-filtered (a security bug).

---

## 13. GDPR / PCI

The strongest section of the original document, and it holds up well under adversarial review — the PCI structural boundary (no raw-PAN column can exist, enforced by both schema and CI-lint) and the audit-fact/actor-directory erasure split are both genuinely sound, credited without reservation.

**One real gap:** the document never addresses **PII surviving in backups**. A tombstone applied to the live `actor_directory`/`customers` tables does nothing to a base backup or WAL archive taken before the erasure request — those retain the original PII for the full backup-retention window (Part 4 §12.2's 35-day rolling window plus longer monthly retention). This is common industry practice *when explicitly documented as an accepted, time-boxed exception* in a DPA — but this document is silent on it entirely, leaving a real compliance question unanswered rather than consciously scoped.

---

## 14. Reporting

- **Materialized views are named but not designed.** No refresh cadence, no mention of `REFRESH MATERIALIZED VIEW CONCURRENTLY`'s requirement for a unique index on the view (meaningfully increasing storage), and no incremental-refresh strategy — for a platform whose value proposition leans heavily on fast, trustworthy reporting, this is underweight relative to its importance.
- **No aggregation/rollup tables exist.** Every report, including multi-branch, multi-year comparisons for 100-branch tenants, is designed to run against raw (if partition-pruned) transactional tables. At real historical volume this is a performance risk that a daily/branch/item sales rollup table would straightforwardly resolve, and its complete absence is a gap.
- The OrderTaxLine gap (§1) directly breaks the Tax/GST report's explicit "by rate" requirement — restated here as a reporting-domain failure, not just a domain-model one.

---

## 15. AI Readiness

- **`pgvector` is never mentioned, despite PostgreSQL 17 being the chosen platform and this review explicitly asking about "Future Vector Search."** Given `pgvector` is a mature, widely-adopted extension and the natural on-ramp for future recommendation-engine and semantic-search features, its complete absence from any discussion is a notable, avoidable gap — even a one-paragraph "deferred, but the extension is available and the migration path is additive" would have been sufficient; total silence is not.
- No sales/demand rollup tables (§14) means demand-forecasting and inventory-prediction features would have to scan raw partitioned history rather than a purpose-built time-series-friendly aggregate — workable, but inefficient, and never acknowledged as a trade-off.
- The outbox-based lineage backbone remains a genuine strength for future traceability — credited, as in the original self-review.

---

## 16. Backup & Recovery — Most Severe Single Finding

**There is no tenant-level or branch-level restore capability. Only whole-cluster point-in-time recovery is designed.**

In a shared-schema, RLS-isolated multi-tenant database (the explicit, deliberate design for the majority of tenants — Part 1 §4.2), a single tenant's data corruption — caused by an application bug, a bad migration, an operator error, anything short of a full-cluster disaster — **cannot be repaired without restoring the entire cluster to a point in time**, which would silently roll back every other tenant sharing that shard as well. This is precisely the scenario a shared multi-tenant architecture is *most* exposed to (one tenant's blast radius bleeding into every other tenant's data), and this document has no answer for it. An Amazon or Google reviewer would treat this as a launch blocker on its own, independent of every other finding in this review.

**Required fix:** a parallel, tenant-scoped logical backup mechanism (scheduled `pg_dump`-style per-tenant exports, or a CDC-based per-tenant replay log built on the same outbox infrastructure already in place) capable of restoring one tenant's data to a point in time without touching any other tenant's rows.

---

## 17. Performance Simulation

| Scenario | Assessment |
|---|---|
| 100 concurrent cashiers | Mitigated by `InventoryItem` being branch-scoped (§4's hot-row risk is naturally bounded to a single branch's small terminal count, not the platform's 100 concurrent total) — a real, positive design property, though never stated as such in the source document. |
| 100 kitchen screens | Architecturally sound via Redis Streams consumer groups; not a data-layer bottleneck. |
| 5,000 simultaneous QR customers | **Cache-stampede risk, unaddressed.** A menu price change or 86-list update invalidates the cache at the exact moment thousands of concurrent QR sessions may re-fetch simultaneously, all missing cache together and hammering Postgres at once. No request-coalescing or lock-on-miss strategy is designed anywhere in this document or its predecessors. |
| Millions of rows / weekend spikes | Partitioning strategy is sound for the partitioned tables; `inventory_items` itself is **not** partitioned and absorbs continuous trigger-driven updates — its autovacuum tuning is mentioned but the resulting bloat under sustained high-frequency updates across millions of rows is asserted as manageable, not demonstrated. |
| Large franchises (100+ branches, one tenant) | **Tier-promotion timing gap (§10) becomes a real bottleneck exposure here** — a large single tenant can remain on shared infrastructure well past the point its own peak-hour load degrades every other tenant on the same shard, with no defined trigger to move it. |

---

## 18. Missing Components (Exhaustive)

Tip/Gratuity entity · ServiceCharge entity · Discount/Promotion entity · ApprovalRequest workflow entity · CurrencyExchangeRate · Branch-level menu/price override · Scheduled-menu (time-of-day pricing) entity · KitchenStation entity + routing rules (currently free-text) · CustomerSegment/Tag entity · WebhookDelivery as a formally catalogued entity · UnitOfMeasure + conversion table · OrderTaxLine (per-rate breakdown) · Recipe cost snapshot at sale time · Transfer-pairing linkage on StockMovement · SupplierReturn entity · GoodsReceipt rejected/returned-quantity tracking · LiquorBottle↔StockMovement foreign key · Negative-inventory CHECK constraint / per-branch allow-negative flag · ON DELETE policy for every foreign key · Composite unique constraints on UserRole/RolePermission/ModifierGroup-MenuItem · Ad-hoc/non-catalog OrderItem support · Cross-batch sync ordering resolution · Device-level revocation/deny-list · Device staleness/loss alerting threshold · Tenant-level and branch-level logical backup/restore · Extended statistics (`CREATE STATISTICS`) on tenant/branch-correlated columns · HOT-update eligibility verification for trigger-updated columns · Write-amplification budget/monitoring · `pgvector` / vector-search readiness statement · Sales/demand rollup (aggregation) tables · Cache-stampede mitigation (request coalescing on cache miss) · Tenant tier-promotion trigger/threshold policy · Documented per-tenant background-job fan-out pattern at scale · Partitioned-table/SQLAlchemy ORM interaction guidance · Backup-retention PII/GDPR policy statement · Materialized view refresh strategy (concurrency, indexing, cadence) · Full column-level table specifications for the ~47 entities not detailed in Part 2 (a completeness gap against the original deliverable's own ambition, even accounting for its explicit "representative tables only" scope reduction).

---

## 19. Risk Register

### Critical

| Risk | Why it exists | Business impact | Technical impact | Likelihood | Mitigation |
|---|---|---|---|---|---|
| No tenant-level/branch-level restore | Shared-schema design only planned cluster-wide PITR | A single tenant's data-corruption incident forces an all-tenant rollback or is simply unrecoverable | Requires a parallel logical backup/CDC-replay mechanism | Medium (software bugs are inevitable at scale) | Build scheduled per-tenant logical export/replay capability before GA |
| LiquorBottle disconnected from StockMovement | Entity cataloged without its consuming relationship being designed | Liquor variance reporting — a named competitive differentiator — cannot ship | Schema change (add nullable FK) before implementation begins | Certain, the moment the Liquor module is built | Add `liquor_bottle_id` to `stock_movements` now |
| No Tip/ServiceCharge/Discount entities | Domain model omitted core commercial-transaction primitives | Cannot process a real-world bill; blocks BR-14 and payroll tip pooling | Requires new columns/entities on Order/Bill before any billing code is written | Certain | Add before Sprint 2 implementation starts |
| Order/Bill aggregate boundary blocks running tabs | Aggregate modeled as strictly one order → many bills | Bar tab workflow (Blueprint B3) cannot be implemented | Requires either a Tab entity above Order, or a many-to-many Order↔Bill join | Certain, the moment Bar module is built | Redesign the aggregate boundary now |
| No cascade/delete rules specified | Omitted from every table spec | Tenant offboarding purge job (already mandated by this same document) will fail on first FK constraint | Requires an explicit, reviewed ON DELETE policy per relationship | High — will be hit the first time offboarding is exercised | Define and apply before implementation |
| Negative inventory unenforced at schema level | Business rule (BR-8) has no CHECK constraint or flag | Overselling out-of-stock items despite a documented rule against it | Add CHECK constraint + per-branch tolerance flag | High under offline/concurrent replay | Add before Inventory module implementation |
| Missing OrderTaxLine (per-rate breakdown) | Tax modeled as one aggregate column | Tax/GST report cannot satisfy its own "by rate" requirement | Requires a new child table | Certain, the moment mixed-tax orders occur | Add before Billing/Tax reporting implementation |
| Cross-batch sync ordering unresolved | Only intra-batch HLC ordering was designed | Data-correctness bug under adverse network conditions — exactly the scenario offline-first exists to survive | Requires explicit inter-batch sequencing design | Medium-high under real-world flaky connectivity | Design before Sync module implementation |
| UserRole/RolePermission missing uniqueness | Universal ULID-PK mixin applied without adjustment for join tables | Duplicate/ambiguous authorization grants possible | Add composite unique constraints (or switch to natural composite PK) | Medium | Fix before Identity module implementation |

### High

| Risk | Why it exists | Business impact | Technical impact | Likelihood | Mitigation |
|---|---|---|---|---|---|
| No recipe-cost snapshot at sale time | Only selling price is snapshotted | Historical food-cost % reports silently misstate margin after any ingredient price change | Add a cost-snapshot column to OrderItem | High — ingredient prices change routinely | Add before Reporting relies on historical food cost |
| Branch-level menu/price override impossible | MenuItem owned by Restaurant with one global price | Contradicts the Blueprint's own Menu Management requirements | Requires a branch-override table or moving pricing ownership to Branch | Certain | Redesign before Menu module implementation |
| No device-level revocation / lost-device workflow | Session revocation modeled only at user level | Un-synced data on a lost device is permanently lost; no kill-switch for the device itself | Add device status/deny-list and staleness alerting | Medium | Design before GA |
| No tenant-level logical backup PII policy for GDPR | Backups retain pre-erasure PII for their full retention window | Compliance ambiguity in EU markets | Requires an explicit, documented policy (accepted exception + time-bound retention) | Medium | Document before EU tenant onboarding |
| CHAR(26) instead of TEXT for all ULID columns | Mechanical application of a fixed-length type | PostgreSQL anti-pattern; comparison/whitespace footguns across 60 tables | Cheap to fix pre-implementation, expensive after data exists | Certain to be flagged in any competent code review later | Fix now |
| No ledger/double-entry structure | Payments/Refunds/Expenses are disconnected single-entry facts | Blocks credible accounting-system integration | Requires a unifying ledger abstraction | Low today, high at Phase 3 (Accounting integrations) | Design before that roadmap phase, not before Sprint 2 |
| No cache-stampede protection | Not designed anywhere in TAD or Data Architecture | Thundering-herd Postgres load spike at 5,000 concurrent QR customers after any cache invalidation | Requires request-coalescing/lock-on-miss pattern | Medium at target scale | Add to caching design before QR-ordering launch |
| No tenant tier-promotion policy | Threshold for shared→dedicated migration undefined | Large tenants can degrade shared-tier neighbors before being moved | Define and monitor concrete thresholds | Medium | Define before onboarding first very-large tenant |

### Medium

Missing UnitOfMeasure conversion (silent cost-calculation errors) · No extended statistics on correlated tenant/branch columns (planner misestimation) · HOT-update eligibility unverified on trigger-updated columns · Write amplification unquantified · Materialized view refresh strategy underspecified · No SupplierReturn / GoodsReceipt rejection tracking · No transfer-pairing linkage on StockMovement · Ambiguous ModifierGroup↔MenuItem relationship · No ad-hoc/custom OrderItem support · Partitioned-table/SQLAlchemy ORM interaction unaddressed · Ambiguous platform-vs-tenant repository base-class scoping.

### Low

No `pgvector`/vector-search readiness statement (future-phase, not blocking) · No sales/demand rollup tables (workable without, just inefficient) · Outbox dispatch-order guarantee under concurrency not formally proven (mitigated by idempotent, order-tolerant consumer design already in place) · StockAdjustment/StockMovement possible redundancy (a simplification opportunity, not a defect).

---

## 20. Improvement Plan

### Immediate (blocking — required before Sprint 2 implementation begins)

1. Add Tip, ServiceCharge, and Discount/Promotion entities and wire them into Order/Bill.
2. Add `liquor_bottle_id` to `stock_movements`, completing the liquor variance data path.
3. Redesign the Order/Bill aggregate boundary to support multi-order tabs.
4. Add `OrderTaxLine` for per-rate tax breakdown.
5. Define and apply an explicit `ON DELETE` policy for every foreign key relationship.
6. Add negative-inventory enforcement (CHECK constraint + per-branch tolerance flag).
7. Fix `UserRole`/`RolePermission` (and any other pure join table) to enforce natural-key uniqueness.
8. Replace `CHAR(26)` with `TEXT` + length `CHECK` across all ULID columns.
9. Design tenant-level/branch-level logical backup and restore, alongside cluster-level PITR.
10. Resolve cross-batch sync ordering explicitly.

### Next Sprint (required before scaled GA, not before initial implementation)

11. Add recipe-cost snapshotting to `OrderItem`.
12. Add branch-level menu/price override and scheduled-menu support.
13. Add `UnitOfMeasure` conversion table.
14. Add device-level revocation/deny-list and staleness alerting.
15. Add `SupplierReturn` and `GoodsReceipt` rejection tracking; add transfer-pairing linkage to `StockMovement`.
16. Resolve the `ModifierGroup`↔`MenuItem` relationship with an explicit join table.
17. Add ad-hoc/non-catalog `OrderItem` support.
18. Formalize materialized-view refresh strategy (concurrency, indexing, cadence).
19. Add extended statistics on correlated `tenant_id`/`branch_id` columns; verify HOT-update eligibility on trigger-updated columns; quantify write amplification.
20. Add cache-stampede mitigation to the caching design.
21. Define concrete tenant tier-promotion thresholds.
22. Complete full column-level table specifications for the remaining ~47 entities.

### Future (Phase 3+, roadmap-aligned)

23. Design a ledger/double-entry structure ahead of Accounting integrations.
24. Add `pgvector` readiness statement and migration path for future recommendation/semantic-search features.
25. Add sales/demand rollup tables ahead of AI forecasting features.
26. Design the data warehouse/CDC pipeline (already flagged as out of scope in the source document — reaffirmed here as necessary before AI Assistant ships).
27. Design cross-shard reporting fan-out/merge logic ahead of the first tenant actually requiring a second shard.

---

## 21. Architecture Score

| Area | Score /10 | Rationale |
|---|---|---|
| Domain Model | 6.5 | Broad, well-organized coverage of 60 entities undermined by real gaps (Tip/Discount/ServiceCharge/ExchangeRate absent, LiquorBottle unwired, Order/Bill aggregate defect) |
| Normalization | 7.5 | Sound in principle, deliberate denormalization well-documented, but the join-table key defect is a genuine flaw |
| Scalability | 7.5 | Excellent sharding/partitioning readiness undercut by the tenant-restore gap and unresolved cross-batch sync ordering |
| Security | 8.5 | The strongest area — PCI/GDPR design holds up under adversarial review; backup-PII policy is the one real gap |
| Performance | 7.0 | Good indexing philosophy; write amplification, HOT updates, extended statistics, and cache-stampede protection are all unaddressed |
| Maintainability | 7.0 | Clean conventions where applied, but inconsistently (join tables, ModifierGroup ambiguity) and incompletely (47 entities lack full specs) |
| Offline Readiness | 7.0 | Genuinely strong core design (HLC, ULID, conflict registry) with real, concrete stress-test failures (concurrent order-total race, cross-batch ordering, lost-device data loss) |
| Multi-Tenancy | 8.0 | The RLS/`SET LOCAL` fix is excellent; the missing tenant-level restore capability is a severe, unresolved counterweight |
| Reporting | 6.0 | Materialized views and rollups are named, not designed; the missing tax-by-rate breakdown directly breaks a stated report requirement |
| AI Readiness | 5.5 | Honest self-assessment undersold the gap; `pgvector` is never even mentioned despite being explicitly in scope for this review |
| Developer Experience | 8.0 | Mixins, repository, and Unit of Work patterns are clean, consistent, and genuinely well-designed |
| Commercial Readiness | 6.0 | Missing Tip/Discount/ServiceCharge is not a gap in a secondary feature — it is a gap in the ability to sell this as a commercial POS today |
| **Overall** | **7.2** | A strong architectural foundation with excellent instincts in multi-tenancy and security, let down by domain-model gaps that block named features outright and one severe operational gap (tenant restore) that a hyperscale reviewer would treat as disqualifying on its own |

---

## Final Recommendation

**Score: 7.2 / 10 — below the 9.5 threshold required for approval.**

# NOT APPROVED FOR IMPLEMENTATION

The 9 Critical and 8 High findings above must be remediated — at minimum, the full "Immediate" list in Section 20 — before Sprint 2 business-logic implementation begins. Several of these are not refinements to an otherwise-sound design; they are the difference between a schema that can and cannot support features this platform has already promised, in writing, across three prior documents (liquor variance reporting, bar tabs, discount workflows, per-rate tax reporting). The board recommends a **Sprint 2.5 — Data Architecture Remediation** pass, mirroring the successful Sprint 1.5 remediation precedent already set for the Technical Architecture, before any table is created in a production or staging environment.

---

*End of document — RestaurantOS Enterprise Data Architecture Review Board Report v1.0*
