# RestaurantOS — Independent Architecture Review Board Report

**Document type:** Production Readiness Review (PRR)
**Reviewed artifacts:** [Product Blueprint v1.0](RestaurantOS_Product_Blueprint.md), [Technical Architecture v1.0](RestaurantOS_Technical_Architecture.md)
**Review posture:** Adversarial. This board's mandate is to find every reason this architecture fails at 10,000 tenants, 1,000,000 customers, and millions of transactions/day — not to validate prior decisions.
**Verdict up front:** The foundation is a **credible, well-documented Phase-1 starting point** — genuinely above average for a pre-Series-A engineering org. It is **not yet production-grade at the stated target scale**, and several gaps are the kind that are cheap to fix today and extremely expensive to fix after Sprint 2 ships real business code on top of them. Two of those gaps (offline-frontend architecture, JWT revocation latency) contradict the Blueprint's own stated core differentiators. Those must be fixed before anything else is built.

---

## 1. System Architecture

**Is Clean Architecture implemented correctly?** Partially. The layer boundaries (Domain → Application → Infrastructure → Presentation) are correctly defined and — credit where due — the CI-enforced import-boundary check (TAD §9.6) is a real, machine-checked guarantee most teams claiming "Clean Architecture" never actually enforce. A Google reviewer would call that out as genuinely good engineering discipline.

But the implementation has a structural flaw that will hurt within two sprints: **the backend folder structure (TAD §3.3) organizes code by *layer* only, not by *bounded context*.** `domain/entities/`, `application/use_cases/`, `infrastructure/database/repositories/` are each single flat folders. Once Menu, Inventory, Orders, CRM, Payroll, and Loyalty all land in the same flat `use_cases/` folder, you get hundreds of files with no structural signal about which business capability owns which code — the exact "big ball of layers" anti-pattern that looks clean in a diagram and becomes unnavigable in practice. Shopify and Amazon both learned this lesson the hard way (Shopify's monolith-decomposition initiative exists *because* of this). **Fix now, before Sprint 2:** restructure to vertical slices — `domain/orders/`, `domain/inventory/`, `domain/crm/`, each containing its own entities/services/ports — with the four horizontal layers as a convention *within* each module, not as the top-level folders themselves.

**Is Modular Monolith the right starting point?** Yes — this is the one call the board unanimously agrees with. Toast and Square both started monolithic; premature microservices decomposition kills more early-stage platforms than monoliths do. The extraction seam described (TAD §12.4) is real *if* the bounded-context restructuring above happens — as currently organized (by layer, not context), the promised "move a folder, stand up a new service" extraction story is **false**. You cannot cleanly extract "Inventory" from a flat `use_cases/` folder containing every module's use cases interleaved.

**What's missing entirely:** an **event-driven backbone**. Every side effect of a state change — cache invalidation, WebSocket push, audit log write, future search-index update, future analytics event — is currently implied to happen synchronously inside the same use case, in the same request. There is no domain event abstraction and no transactional outbox pattern. This means:
- A crash after the DB commit but before the WebSocket publish silently drops a KDS ticket update — no retry, no record it ever should have happened.
- Cache invalidation and the DB write are two separate operations with no guaranteed ordering or atomicity — a classic dual-write bug, and the exact kind of bug that causes overselling out-of-stock items (directly violating Blueprint BR-8).

**Redesign required:** introduce a transactional outbox table (written in the *same* DB transaction as the business change) with a relay process (a Celery Beat-scheduled poller, or Postgres logical replication/CDC later) that reliably publishes events to Redis/WebSocket/cache-invalidation consumers. This is not optional polish — it's the mechanism that makes "one source of truth, many surfaces" (Blueprint §2) actually true under failure conditions instead of just under happy-path demos.

Also missing: **CQRS separation for read-heavy paths.** Reporting and the Cloud Dashboard query the same write-optimized OLTP schema and (per TAD §5.9) the same read replica as ad hoc queries. At "millions of transactions/day," letting arbitrary report queries run against the transactional replica without a read-model/materialized-view strategy is a recipe for the reporting feature degrading POS-adjacent read performance the moment a chain owner opens a 90-day multi-branch report.

---

## 2. Scalability

**Ranked by which one breaks first at 10,000 tenants / millions of transactions per day:**

1. **PostgreSQL (primary, writes) — breaks first, and the architecture has no real answer for it.** Shared-schema, row-level multi-tenancy on a single logical primary is a reasonable Phase-1 choice, but the TAD's only stated scaling lever for the database is "add a read replica" and, later, "add PgBouncer." Neither addresses **write** throughput, which is what a POS system actually stresses (every order, every payment, every stock deduction is a write). There is no sharding key, no partitioning plan, and no stated ceiling at which a second Postgres cluster gets introduced. A Stripe or Shopify engineer reviewing this would ask, on day one: "what's your tenant-to-shard mapping?" — and today there is no answer.

2. **Redis — a close second, for a self-inflicted reason.** The architecture uses **one Redis** for cache, Celery broker, and Pub/Sub fan-out (TAD §4, §5.9–5.11). These three workloads have incompatible operational profiles: the broker needs durability and can spike in memory usage under queue backlog; the cache wants LRU eviction under memory pressure; Pub/Sub wants low latency and doesn't tolerate the instance being busy evicting cache keys or persisting broker state. Under real load, a broker backlog (e.g., a burst of nightly report jobs) can evict hot cache keys, which then dumps load back onto Postgres — a cascading failure with Redis in the middle of it. **This must be split into at least two, ideally three, separate Redis instances/clusters before production traffic**, not deferred to a "future" scaling trigger.

3. **WebSocket delivery guarantees** — the design (TAD §5.11) explicitly acknowledges "best-effort" event replay on reconnect with no real mechanism behind that phrase. Redis Pub/Sub has zero message persistence: a KDS terminal that drops its socket for even a few seconds during a Wi-Fi hiccup **permanently loses** any ticket-status events published during that gap, with nothing to replay from. For a Kitchen Display System — where a missed "ticket ready" event means a dish sits under a heat lamp until someone notices — this is a correctness gap, not a nice-to-have. Redis Streams (with consumer groups and an actual replay cursor) or a durable queue is the right primitive here, not Pub/Sub.

4. **Celery at the stated volume** is a known operational pain point past a certain throughput (broker overhead, visibility-timeout tuning, limited built-in observability compared to purpose-built stream platforms). Not an immediate blocker, but the panel flags it as a **medium-term** risk to revisit once background job volume is empirically measured — not a Phase-1 blocker.

5. **API layer** is the *least* concerning tier — it's correctly stateless and horizontally scalable from day one. **Object storage** is similarly low-risk given S3-compatible storage's inherent horizontal scalability.

**Additional scalability gap:** connection pooling (PgBouncer) is filed under "Future Scaling Strategy" (TAD §12.2) as something triggered *later*. That's backwards. With multiple horizontally-scaled async API replicas each holding their own SQLAlchemy connection pool, Postgres's default `max_connections` ceiling is realistically hit at a *small* number of replicas, long before "10,000 tenants" — this should be a **Phase-1 Day-1** component, not a scaling-trigger response. (It also interacts badly with the RLS design — see Section 3.)

---

## 3. Multi-Tenancy

The two-layer model (application-enforced scoping + PostgreSQL RLS as defense-in-depth) is directionally correct and better than most Series-A SaaS companies' actual implementations. The review board's objections are about what's *missing* around that core idea, not the core idea itself.

**Critical gap — RLS and connection pooling are incompatible as currently specified.** Postgres RLS policies keyed on a session variable (e.g., `current_setting('app.tenant_id')`) require that variable to be set correctly for *every* query on *every* connection. PgBouncer in transaction-pooling mode (the mode you need for real concurrency at scale) does **not** guarantee that a session variable set by one logical request persists correctly to the next logical transaction on a reused physical connection — this is a well-known, well-documented failure mode. The TAD introduces PgBouncer (§12.2) as a future scaling lever *without ever addressing this interaction with the RLS mechanism it depends on for tenant isolation* (§5.12). If this isn't solved architecturally now, the day PgBouncer is turned on is the day tenant isolation silently breaks. **This needs a designed answer before Sprint 2**, not a footnote — options include session-mode pooling scoped per tenant, explicit tenant_id parameterization in every query as the *sole* enforcement mechanism (demoting RLS to pure defense-in-depth verified by periodic audit rather than a load-bearing runtime guarantee), or a pooler that supports the pattern correctly (e.g., PgBouncer's newer session-variable handling, or pgcat).

**Missing — background workers and RLS.** Celery workers that run cross-tenant batch jobs (nightly aggregation, scheduled reports across *all* tenants) almost certainly need a database role that can see multiple tenants' rows, meaning they likely run with RLS bypassed or under a superuser-equivalent role. That reintroduces exactly the cross-tenant leak risk RLS exists to prevent, entirely inside a code path (background jobs) that gets far less scrutiny than API request handlers. This needs an explicit worker-side tenant-scoping discipline, documented and code-reviewed as strictly as the API layer's.

**Missing — tenant tiering.** The architecture treats a single-location café and a 500-branch enterprise chain identically at the infrastructure level (shared schema, shared everything). That's fine for the café. It is **not** fine for the enterprise deals this platform needs to win a billion-dollar valuation: enterprise procurement will ask about dedicated backups, noisy-neighbor isolation, and sometimes dedicated infrastructure for compliance reasons. There is no tiering model (pooled vs. siloed schema vs. dedicated database) anywhere in the document. Shopify Plus and Toast's enterprise tier both required exactly this kind of tiering to close large accounts.

**Missing — noisy-neighbor protection.** No per-tenant query timeout, no per-tenant resource quota, no isolation between a large chain's heavy reporting query and a small café's POS transaction sharing the same primary. At 10,000 tenants this is not hypothetical — it will happen in month one of real scale.

**Missing — read-after-write consistency across the tenant's own data.** If reporting reads from a replica (TAD §12.2) and a manager expects to see a transaction they *just rang up* reflected in a "live" dashboard (Blueprint M1: "live dashboard... real-time"), replication lag directly contradicts the product promise. No strategy (sticky-read-to-primary window, synchronous replica for critical reads, etc.) is defined.

---

## 4. Security

This section gets the most red ink. Several items here are the difference between "passes a SOC 2 audit" and "gets rejected by an enterprise security questionnaire on page one."

| Area | Weakness |
|---|---|
| **JWT / RBAC — CRITICAL, concrete bug** | TAD §8.3 states JWT claims include `roles` directly in the token payload, and access tokens are stateless with a ~15-minute TTL. This directly contradicts Blueprint requirement S1 ("deactivate staff accounts... immediately") and BR-5/general RBAC expectations: **a deactivated employee, or one whose role/permissions just got downgraded, retains their old permissions for up to 15 minutes** because nothing checks the token against current state — it's purely a signature+expiry check by design (§5.13 step 7). For a system whose personas include "fired cashier with till access," this is not a theoretical risk. **Fix:** never embed authorization-relevant claims in a long-lived-enough token without a revocation check; either (a) keep the JWT to identity claims only and look up current roles/permissions from a Redis-cached (short TTL, actively invalidated on change) source on every request, or (b) include a `token_version`/`permission_version` claim that's checked against a live value on every request and bump it on any permission-affecting change, forcing immediate re-auth. |
| **PIN-based login — undesigned attack surface** | The Blueprint calls for PIN quick-login for floor staff (§3.3, shared terminals). The TAD's entire auth section is written as if all auth were email/password + JWT. A 4–6 digit PIN is trivially brute-forceable without terminal-scoped lockout, rate limiting, and a deliberately different (shorter-lived, more restricted) token profile than a back-office login. This is currently **undesigned**, not just under-specified. |
| **PCI scope — undecided, and it matters enormously** | Neither document states whether card data ever transits the RestaurantOS backend (even transiently) during POS or QR checkout. If it does, the company lands in a materially larger PCI DSS audit scope (SAQ D-level) than if client-side tokenization (Stripe Elements / Adyen Web Components-style, card data going straight from browser/terminal to the payment processor) is mandated architecturally. Every payments-literate reviewer on this panel (Stripe, Square) would stop the review here and require this decision **before writing another line of payment-adjacent code.** **Recommendation: mandate client-side tokenization as a hard architectural constraint — the RestaurantOS domain model must never contain a raw PAN field, ever, in any layer.** |
| **GDPR vs. immutable audit log — real conflict, unaddressed** | Blueprint BR-15 and TAD §8.12 mandate audit logs are "never deleted, no exceptions." GDPR's right to erasure applies to personal data appearing in those same logs (a customer's name in a refund entry, a guest's info in a comp reason). As written, these two requirements are in direct conflict for any EU-serving tenant. **Fix:** separate the immutable *financial fact* (amount, timestamp, action code — which legitimately must never be erasable for audit/tax reasons) from *personal identifiers*, which must be pseudonymizable/erasable on request without breaking the financial record's integrity. |
| **Data residency** | No region-sharding or per-region deployment story exists. A single global Postgres primary is incompatible with EU data residency requirements the moment there's an EU tenant. |
| **No WAF** | Nginx is described as the sole edge layer (TAD §7, §11.2). No web application firewall (Cloudflare/AWS WAF/etc.) sits in front of it. For a payments-adjacent, publicly-reachable guest-ordering surface, this is a baseline expectation the panel considers missing, not optional. |
| **No secrets/dependency scanning in CI** | The CI/CD pipeline (TAD §9.6) covers lint, type-check, tests, and image vulnerability scanning — but never source dependency scanning (Dependabot/Snyk/pip-audit) or secrets scanning (gitleaks/truffleHog) on every commit. Both are table-stakes for 2026-era CI/CD and are currently absent. |
| **No JWKS / key rotation mechanism** | RS256 is the right call (§8.3), but there's no `kid`-based key rotation / JWKS endpoint design, meaning a key rotation event today would be a manual, coordinated, likely-downtime operation rather than a routine, zero-downtime one. |
| **MFA is claimed, not designed** | Blueprint mentions MFA availability for back-office roles; the TAD's auth flow diagrams never show a step-up MFA challenge anywhere in the login sequence. |
| **Permission check caching strategy undefined** | RBAC (§8.11) describes a `require_permission()` dependency but never states where the permission set is sourced from per-request — DB hit every request, or cached? Combined with the JWT-embedded-roles bug above, this is the second half of the same unresolved problem: *where does the system get the truth about a user's current permissions, and how fast does a change propagate?* |
| **Field-level encryption** | "Encryption at rest" is stated at the infrastructure level (disk/DB encryption) but nothing addresses application-level encryption for specific highly sensitive fields (e.g., banking details for expense reimbursement, once that feature exists). Disk encryption alone doesn't protect against a compromised DB credential; field-level encryption/tokenization for the most sensitive columns should be a stated pattern now, before those columns exist. |

**OWASP Top 10 coverage:** injection (SQLi) and XSS are genuinely well covered (§8.8–8.9, ORM-only + CSP + React escaping). Broken access control is the weakest link given the JWT/RBAC revocation gap above. Security misconfiguration risk is elevated by the missing WAF/secrets-scanning items. Cryptographic failures risk is elevated by the missing field-level encryption and JWKS rotation story.

---

## 5. Database Strategy

The TAD is explicit that no schema exists yet — this review is strictly about whether the *architecture* leaves room for the following, and the honest answer is **partially**.

| Concern | Assessment |
|---|---|
| **Sharding** | Not designed at all. No tenant-to-shard mapping, no stated shard key, no abstraction in the repository layer that would make introducing sharding later anything less than a major rewrite. At the stated scale target this needs at least a *documented intent* (e.g., "tenant_id will be the shard key; repositories will be written to never assume a single global connection" as a coding rule) even if actual sharding is deferred. |
| **Read replicas** | Designed (TAD §5.1, §12.2) but incompletely — no replica-lag/read-after-write consistency policy (Section 3 above), which matters more than the mere existence of a replica connection. |
| **Partitioning** | Not addressed anywhere. High-volume, ever-growing, append-only tables (orders, audit logs, future analytics events) have no time-based or tenant-based partitioning plan. Left unaddressed, these become the tables that make `VACUUM`, index maintenance, and query planning progressively worse over years of production data — a slow-motion outage, not a sudden one. |
| **Indexes** | The principle ("every filterable/sortable field is indexed," TAD §5.8) is right, but there's no counter-balancing discussion of write-amplification cost from over-indexing high-throughput tables, nor a stated process for reviewing index bloat/usage over time. |
| **Archiving** | Backups are covered (TAD §15); cold-storage archiving of old transactional data is not. Unbounded primary-table growth across 10,000 tenants over multiple years is a real capacity and performance problem with no stated mitigation. |
| **Soft delete** | Not addressed as a cross-cutting convention anywhere. Given BR-2 implies orders are never hard-deleted, there needs to be an explicit, consistent soft-delete/append-only pattern (and matching RLS/query defaults that exclude soft-deleted rows unless explicitly requested) defined once, centrally — not reinvented per module in Sprint 2. |

---

## 6. DevOps

Genuinely one of the stronger sections of the TAD — the CI/CD pipeline (§9.6), the architecture-boundary lint check, and the immutable-image-promotion model are all sound, current best practice. The gaps are about *rigor at the edges*, not fundamental design:

- **Disaster recovery is aspirational, not concrete.** "RTO/RPO are defined" is asserted (§15) but no actual numbers appear anywhere in either document, and there is no mention of a tested failover drill or game-day exercise. An untested DR plan is not a DR plan — it's a hope. This needs concrete numbers and a rehearsal cadence before this platform holds a single paying enterprise customer's data.
- **No backup-restore testing cadence.** Having backups and having *verified-restorable* backups are different claims; only the former is made.
- **Deployment strategy stops at rolling deploys with health-check-gated rollback** (§11.3). At payments-adjacent scale, the industry norm is canary releases gated on *business* metrics (error rate, transaction success rate), not just infrastructure health checks — a deploy can pass every health check while quietly breaking payment processing logic.
- **No SLOs/error budgets.** Prometheus/Grafana/Sentry/OTel are all named (§10 of the TAD, referenced), but without defined SLOs there's no objective trigger for "stop shipping features, fix reliability" — a decision every mature platform team needs codified, not vibes-based.
- **No cost/FinOps observability.** At the target scale, cloud spend becomes a first-class operational concern; nothing in the DevOps section addresses tracking or alerting on cost anomalies.
- **No production-data-safe staging strategy.** Migration testing against production-representative data volume, and anonymized-production-data-in-staging practices (relevant to GDPR too), are both unaddressed.

---

## 7. Frontend

**This is the single most consequential gap in the entire foundation.** The Blueprint's #1 stated design principle (§2) is "offline-first, cloud-always" — POS and KDS must work with *zero* connectivity. The Frontend Architecture section of the TAD (§6) never once mentions a service worker, IndexedDB, local-first data store, background sync, or conflict-resolution UI. It describes a standard server-connected Next.js application with TanStack Query for server state and Zustand for client state — an architecture that, as written, **stops working the instant the network drops**, which is precisely the scenario the entire product is supposed to survive.

Compounding this: **Next.js App Router Server Components are the wrong default for the POS/KDS apps specifically.** Server Components require a server round-trip by definition — that's antithetical to offline operation. Applying one uniform Next.js strategy across `admin-web` (where Server Components are a fine, even good, choice for data-heavy reporting) and `kitchen-display`/`customer-ordering`'s POS-adjacent surfaces (where a local-first, mostly-client-rendered PWA architecture is required) is an architectural mismatch that needs to be resolved — likely by treating the speed-mode apps as client-heavy PWAs with a local data layer (e.g., IndexedDB via a sync-capable local store) and reserving Server Components for genuinely server-dependent, non-offline-critical back-office screens.

Other gaps, secondary to the one above:
- **No frontend performance budget enforced in CI** (no Lighthouse CI or equivalent) despite the Blueprint making sub-10-second billing and sub-150ms search explicit, measurable product requirements — there's currently nothing stopping a future PR from silently regressing them.
- **No automated accessibility testing** (axe-core or equivalent) despite WCAG 2.1 AA being a stated NFR.
- **No persisted query cache** for offline reads — ties directly back to the primary gap above; TanStack Query's in-memory cache alone doesn't survive a page reload or true offline session.

Accessibility and state-management *design* (the TanStack Query/Zustand split, Section 6.4) are otherwise sound and the board has no objection to them in isolation — the objection is that the whole frontend section was designed for a connected world, in a product whose central promise is functioning in a disconnected one.

---

## 8. Backend

The backend foundation is the most mature part of the TAD. FastAPI structure, DI via `Depends()`, Pydantic-v2 validation at every boundary, the standardized response envelope, and the middleware ordering are all sound, idiomatic, and defensible choices — no material objection from this panel on those specific mechanics.

Remaining gaps, layered on top of the architectural ones already raised in Sections 1–3:

- **No idempotency-key support on synchronous write endpoints.** TAD §5.10 designs idempotency *only* for Celery background tasks. The single most important place for idempotency in this entire system — the POS order-creation/payment endpoint, which offline terminals will *replay* on reconnect per the Blueprint's own offline-first design — has no stated idempotency mechanism at all. This is a direct contradiction: the product's core resilience feature (queue offline, replay on reconnect) depends on exactly the guarantee that's missing from exactly the endpoint that needs it most.
- **No mobile API backward-compatibility policy.** Once the Flutter app ships to app stores, RestaurantOS does not control when users update it — old app versions will call the backend for weeks or months after a new version ships. There's no stated API contract-stability commitment or contract testing (e.g., Pact) protecting against breaking those old clients.
- **No LLM/AI-Assistant cost or quota governance** anywhere in the request/rate-limiting design, despite the AI Business Assistant being a named Phase-3 module — this will have real, variable unit-economics impact and needs a governance hook designed into the API/rate-limiting layer before that module exists, not after a cost incident.
- **API versioning deprecation policy** is directional ("Deprecation/Sunset headers") but lacks a concrete support-window commitment or traffic-monitoring trigger for actually removing a version.

---

## 9. Future Features — Does the Foundation Actually Support Them?

| Feature | Verdict | Why |
|---|---|---|
| Inventory / Liquor Tracking | ✅ Supported, conditional on Section 1's module restructuring happening first | Recipe/BOM-driven deduction fits the Application-layer use-case model cleanly once organized by bounded context. |
| Kitchen Display System | ⚠️ At risk | Core business logic fits fine; the *delivery guarantee* it depends on (Section 2's WebSocket/Pub/Sub gap) is not yet reliable enough for a "ticket silently vanished" failure mode to be acceptable. |
| AI Business Assistant | ❌ Not actually feasible as designed | No analytics/data-warehouse plan exists. Natural-language queries against the OLTP primary or its replica, at "millions of transactions/day," will either be slow or actively harmful to transactional performance. This needs a CDC/ETL pipeline into an analytical store (e.g., ClickHouse, BigQuery, or a Postgres-based OLAP extension) designed *before* this module is scoped, not discovered as a surprise in Phase 3. |
| Payroll | ✅ Supported | Straightforward CRUD/export use cases; no foundation gap specific to this feature. |
| Reservations | ✅ Supported | Same. |
| CRM / Loyalty | ✅ Supported | Same, though campaign messaging (SMS/email at volume) will need its own rate-limiting/quota design against the external provider — not yet addressed but low complexity to add. |
| Online/QR Ordering | ⚠️ At risk | Directly inherits the PCI-scope-undecided risk (Section 4) and the frontend offline gap for degraded-connectivity guest experience. |
| Mobile App | ⚠️ At risk | Inherits the mobile API backward-compatibility gap (Section 8). |
| White-Label Deployments | ⚠️ Partially supported | Theming architecture (CSS variables) supports visual white-labeling; there's no tenant-specific domain routing design and no tenant-tiering/dedicated-infrastructure story (Section 3) that large white-label customers will likely require contractually. |
| Marketplace / Accounting Integrations | ⚠️ Partially supported | The adapter pattern (`infrastructure/external/`) is the right shape, but there's no webhook *ingestion* architecture (signature verification, replay protection, dead-lettering) for inbound events from these integrations — currently only outbound adapter calls are designed. |
| Payment Gateways | ❌ Blocked pending a decision | Cannot be responsibly built until the PCI-scope question (Section 4) is explicitly answered as an architectural constraint. |

---

## 10. Missing Components

Nothing omitted for being "too small," per the brief:

- Event-driven backbone / domain events / **transactional outbox pattern**
- CQRS / read-model separation for reporting vs. OLTP
- Bounded-context (vertical-slice) module structure in the backend codebase
- Analytics/data-warehouse pipeline (CDC/ETL) to support AI Assistant and heavy reporting
- **Offline-first frontend architecture** (service workers, local-first store, sync queue, conflict-resolution UI) — the single biggest gap in the whole foundation
- Idempotency-key support on synchronous write endpoints (POS order/payment creation specifically)
- JWT/RBAC immediate-revocation mechanism (permission versioning or live lookup, not embedded stale roles)
- PIN-based auth security model (lockout, terminal-scoped rate limiting, distinct token profile)
- MFA step-up flow design
- JWKS endpoint / automated key rotation
- Explicit PCI-scope decision + enforcement (no raw PAN in the domain model, ever)
- GDPR data-subject-rights architecture (erasure vs. immutable-audit-log reconciliation via pseudonymization)
- Data residency / regional deployment strategy
- Tenant tiering model (pooled vs. dedicated) for enterprise customers
- Noisy-neighbor protection / per-tenant query timeouts and resource quotas
- RLS + connection-pooling compatibility plan (before PgBouncer is introduced)
- Read-after-write consistency policy for replica reads
- Database sharding strategy (at least a documented shard key and repository-layer discipline)
- Table partitioning strategy for high-volume append-only tables
- Data archiving / cold-storage strategy
- Soft-delete as a documented cross-cutting convention
- WAF at the edge
- Secrets scanning + dependency vulnerability scanning in CI
- Concrete DR RTO/RPO targets + rehearsed failover drills
- Backup-restore verification cadence
- Canary/blue-green deployment gated on business metrics, not just health checks
- SLOs / error budgets
- Cost/FinOps observability
- Frontend performance budgets enforced in CI (Lighthouse CI or equivalent)
- Automated accessibility testing (axe-core or equivalent)
- Mobile API backward-compatibility policy + consumer-driven contract testing
- LLM/AI cost and quota governance hook
- Webhook ingestion framework (signature verification, replay protection, dead-lettering) for inbound third-party events
- Multi-gateway payment abstraction detail (beyond the generic adapter folder)
- Money/currency value-object rounding and precision rules
- Clock-skew / time-synchronization strategy for offline-terminal event ordering
- Hardware integration abstraction (receipt printers, cash drawers, barcode scanners — ESC/POS or equivalent protocol layer)
- Redis workload separation (cache vs. broker vs. Pub/Sub as distinct instances/clusters)
- Field-level encryption/tokenization pattern for future highly sensitive columns

---

## 11. Risk Assessment

### High Risk

| Risk | Why risky | Business impact | Technical impact | Fix |
|---|---|---|---|---|
| Stale permissions in stateless JWT (up to 15 min) | Deactivation/role-change isn't enforced until token expiry | Terminated/demoted staff retain access; fraud and compliance exposure | Requires either token-version checking or live permission lookup added to auth middleware | Add a `permission_version` claim checked against a live (Redis-cached, actively invalidated) value on every request |
| No offline-first frontend architecture | Contradicts the product's central differentiator | POS/KDS may not actually survive a network outage — the flagship promise | Section 6 needs a full local-first redesign for speed-mode apps before Sprint 2 builds POS UI on top of it | Introduce a local-first data layer (service worker + IndexedDB-backed store + sync queue) for POS/KDS/QR-ordering apps specifically |
| PCI scope undecided | Determines audit burden, cost, and time-to-launch for any payment feature | Could force full PCI DSS Level 1 scope instead of minimal SAQ-A | Payment flows must be redesigned around client-side tokenization if not already | Mandate client-side tokenization as a hard constraint now, before any payment code is written |
| RLS incompatible with planned connection pooling | Silent tenant-isolation failure once PgBouncer is introduced | A cross-tenant data leak is a company-ending event for a multi-tenant SaaS | Requires resolving before PgBouncer (a "future" item) is actually turned on | Choose session-mode pooling for tenant-scoped connections, or make application-layer scoping the sole load-bearing mechanism with RLS as audited defense-in-depth |
| No transactional outbox / event backbone | Dual-write inconsistency between DB commit and cache/WebSocket/audit fan-out | Overselling out-of-stock items (violates BR-8), missed KDS tickets | Retrofitting an outbox after multiple modules exist is a much larger project than building it first | Build the outbox pattern as part of the foundation, before the first business module |
| No sharding/partitioning strategy at 10,000-tenant target | Single Postgres primary write-scaling ceiling | Platform-wide outage or severe degradation once real scale is reached | Migration under production load is far more painful than designing for it upfront | Document a tenant-based shard key and repository-layer discipline now; defer *execution* until needed |
| No idempotency on synchronous write endpoints (esp. order/payment creation) | Offline terminals are designed to replay writes on reconnect | Double-charged customers, double-deducted stock | Needs an idempotency-key mechanism on every write endpoint that offline clients can queue | Extend the idempotency pattern already designed for Celery tasks to all synchronous mutation endpoints |
| GDPR erasure vs. immutable audit log conflict | Legal exposure in any EU-serving tenant | Regulatory fines, blocked EU expansion | Requires separating PII from immutable financial facts in the audit design | Pseudonymize/tokenize PII fields in audit entries; keep only financial facts truly immutable |

### Medium Risk

| Risk | Why risky | Business impact | Technical impact | Fix |
|---|---|---|---|---|
| Redis serving cache + broker + Pub/Sub on one instance | Workload contention under load | Cascading failures during traffic spikes | Requires infra topology change | Split into separate Redis instances/clusters per concern |
| Backend organized by layer, not bounded context | Codebase becomes unnavigable as modules multiply | Slower feature delivery over time | Large refactor if deferred too long | Restructure to vertical-slice modules now, before Sprint 2 |
| No analytics/data-warehouse plan for AI Assistant | Roadmap feature may be technically infeasible as scoped | Phase-3 roadmap slips or ships broken | Requires a CDC/ETL pipeline design | Plan a warehouse/OLAP pipeline before AI Assistant is scoped in detail |
| No mobile API backward-compatibility policy | Old app versions in the field break silently | App store reviews, support burden, churn | Requires versioning discipline + contract tests | Define a minimum-supported-version window and add consumer-driven contract testing |
| DR plan lacks concrete RTO/RPO and drills | Untested DR is unproven DR | Extended outage during a real disaster | Requires defining numbers and running game days | Set concrete targets, schedule rehearsed failover drills |
| No WAF, secrets scanning, or dependency scanning | Common attack surface left uncovered | Increased breach risk | Requires adding tooling to CI/edge | Add WAF at edge; add gitleaks/Dependabot-equivalent to CI |
| No noisy-neighbor protection between tenants | One tenant's heavy usage degrades others | Enterprise customer SLA violations | Requires per-tenant quotas/timeouts | Add statement timeouts and per-tenant rate/resource limits |

### Low Risk

| Risk | Why risky | Business impact | Technical impact | Fix |
|---|---|---|---|---|
| No frontend performance budget in CI | Perf regressions ship unnoticed | Slow erosion of the "fast POS" promise | Requires adding Lighthouse CI | Add automated performance budget checks |
| No automated accessibility testing | WCAG compliance drifts over time | Legal/compliance exposure, smaller than the items above | Requires adding axe-core to CI | Add automated a11y checks to CI |
| No cost/FinOps observability | Cloud spend surprises at scale | Margin erosion, not an outage | Requires adding cost dashboards/alerts | Add billing anomaly alerting once real usage exists |
| API version deprecation policy lacks concrete numbers | Ambiguity in when old versions can be removed | Minor coordination friction | Low — mostly a documentation fix | Define and publish a concrete support-window SLA |

---

## 12. Score the Architecture

| Area | Score /10 | Rationale |
|---|---|---|
| **Architecture** | 6.5 | Correct Clean Architecture layers and a genuinely enforced boundary check, undercut by layer-only (not bounded-context) organization and a missing event-driven backbone. |
| **Scalability** | 5.0 | Stateless services scale fine; the database and Redis have no real story past "add a replica" at a stated 10,000-tenant target. |
| **Maintainability** | 6.0 | Strong today; will degrade quickly once dozens of modules share flat, non-modular folders unless restructured first. |
| **Security** | 5.0 | Good bones (RS256, RBAC, RLS, audit logging) undermined by a concrete revocation-latency bug, an undecided PCI scope, and missing WAF/scanning basics. |
| **Performance** | 6.0 | Backend performance targets are concrete and reasonable; the frontend's offline-first performance promise is currently undesigned. |
| **Developer Experience** | 7.5 | The strongest area — monorepo, typed contracts, DI, enforced standards, and a clean local dev loop are all genuinely good. |
| **Operations** | 5.5 | Solid CI/CD skeleton; DR, SLOs, and cost observability are aspirational rather than concrete. |
| **Documentation** | 8.0 | Thorough, diagrammed, and consistently traceable back to the Product Blueprint — a real strength worth preserving as the system grows. |
| **Commercial Readiness** | 4.5 | The PCI, GDPR, tenant-tiering, and DR gaps are exactly the questions that stall enterprise deals and compliance audits — not yet closeable with a straight face today. |
| **Overall** | **5.8 / 10** | A strong, well-documented Phase-1 skeleton that is not yet safe to build a billion-dollar SaaS platform's business logic on top of without addressing the Critical items in Section 13 first. |

---

## 13. Improvement Plan

### Critical — block Sprint 2 (fix before any business module is built)

1. Fix JWT/RBAC revocation latency (permission-version check or live lookup, not embedded stale roles).
2. Design the offline-first frontend architecture properly (local-first store, sync queue, service worker) for POS/KDS/QR-ordering apps specifically — before their UI is built on top of the current connected-only assumption.
3. Decide and enforce the PCI scope constraint (client-side tokenization; no raw PAN in the domain model, ever).
4. Build the transactional outbox pattern for reliable event fan-out (cache invalidation, WebSocket push, audit consistency).
5. Restructure the backend into bounded-context vertical slices instead of flat architectural layers.
6. Resolve the RLS + connection-pooling compatibility question before PgBouncer is introduced.
7. Design the GDPR erasure vs. immutable-audit-log reconciliation (PII pseudonymization pattern).
8. Add idempotency-key support to synchronous write endpoints, especially order/payment creation.

### Important — fix within Phase 1–2, before real scale hits

9. Document a Postgres sharding key and repository-layer discipline (even if execution is deferred).
10. Split Redis into separate cache/broker/Pub/Sub instances.
11. Define a read-after-write consistency policy for replica reads.
12. Add WAF, secrets scanning, and dependency vulnerability scanning.
13. Define concrete DR RTO/RPO targets and schedule rehearsed failover drills.
14. Define a mobile API backward-compatibility policy and add consumer-driven contract testing.
15. Define a tenant-tiering model (pooled vs. dedicated) for enterprise customers.
16. Plan the analytics/data-warehouse pipeline required for the AI Assistant and heavy reporting.
17. Design a webhook ingestion framework (signature verification, replay protection, dead-lettering) for future integrations.
18. Add table partitioning and archiving strategy for high-volume append-only tables.

### Nice to Have — Phase 3–4 polish

19. Frontend performance budgets enforced in CI (Lighthouse CI).
20. Automated accessibility testing (axe-core) in CI.
21. SLOs/error budgets and a formalized on-call escalation policy.
22. Cost/FinOps observability and anomaly alerting.
23. Canary/blue-green deployment gated on business metrics, not just health checks.
24. JWKS endpoint and automated key-rotation tooling.
25. Hardware integration abstraction layer (receipt printers, cash drawers, barcode scanners).
26. LLM/AI cost and quota governance hook ahead of the AI Assistant module.

---

*End of document — RestaurantOS Independent Architecture Review Board Report v1.0*
