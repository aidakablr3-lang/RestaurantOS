# Onboarding co-pilot — build spec

> Drop this file at `docs/ONBOARDING_COPILOT_SPEC.md` in your repo.
> Then run the phase prompts below, one at a time, reviewing between each.

---

## 0. Fill this in before starting

Replace the bracketed values. Claude Code will read the rest from the codebase.

```
Repo:              [path]
Backend stack:     [e.g. NestJS + Postgres + Prisma]
Frontend stack:    [e.g. Next.js + React + Tailwind]
Auth model:        [e.g. JWT, tenant-scoped, role claims]
Existing API base: [e.g. src/modules/*/  with REST controllers]
Who runs the co-pilot: [internal onboarding team | client self-serve]
LLM access:        [Anthropic API key available as ANTHROPIC_API_KEY | none yet]
Deployment:        [e.g. single-tenant-per-schema | shared schema with tenant_id]
```

---

## 1. What we are building

A co-pilot that takes a brand-new restaurant client from zero to a verified,
live tenant. It must:

1. Know the onboarding dependency graph and what is currently blocked/ready.
2. Execute steps itself against the existing service layer — never raw SQL.
3. **Verify** every step by reading state back, not by trusting the write.
4. Resume cleanly after interruption, at any point, without duplicating records.
5. Bulk-ingest the heavy content (menu, inventory, recipes, staff, tables).
6. Refuse to hand over until an automated end-to-end smoke test passes.

## 2. The dependency graph

Sequential spine:

```
create_tenant → create_owner → create_restaurant → create_branch
```

Then four parallel tracks, all depending only on `create_branch`:

| Track | Steps |
|---|---|
| Locale | `configure_currency` → `configure_tax` |
| Floor | `create_tables` → `generate_qr_codes` |
| People | `create_manager`, `create_waiters`, `create_kitchen_staff` (all parallel) |
| Catalog | `add_menu`, `add_inventory` (parallel) → `add_recipes` (needs both) |

All four tracks converge on:

```
smoke_test  (gate — must pass)  →  client_handover
```

Two deliberate deviations from the naive linear flow:

- **No interactive "owner login" step.** The co-pilot acts under a scoped,
  time-boxed onboarding token with full audit logging. The owner's first real
  login happens at handover.
- **Currency and tax are defaulted, not asked.** Country `IN` implies INR,
  CGST/SGST split, standard restaurant GST slabs, and HSN defaults. Present a
  one-line confirmation with an edit affordance instead of a form.

## 3. Core abstraction: the step registry

Every step is a record implementing one contract. No step logic lives in UI
components or in the LLM prompt.

```ts
type StepId = 'create_tenant' | 'create_owner' | /* ... */;

interface OnboardingStep<TInput, TOutput> {
  id: StepId;
  title: string;
  requires: StepId[];

  /** Zod schema of fields that must be collected from a human. */
  collect: ZodSchema<TInput>;

  /** Derive defaults from run context so we ask as few questions as possible. */
  autofill?(ctx: RunContext): Partial<TInput>;

  /** Perform the mutation. MUST be idempotent via idempotencyKey. */
  execute(input: TInput, ctx: RunContext): Promise<TOutput>;

  /** Read state back and assert it is correct. Returns a structured result. */
  verify(ctx: RunContext): Promise<VerifyResult>;

  /** Best-effort rollback for failed or abandoned runs. */
  undo?(ctx: RunContext): Promise<void>;

  /** True if this step can be executed with zero human input. */
  autonomous?: boolean;
}

type VerifyResult =
  | { ok: true; evidence: string }        // e.g. "GET /branches/17 → status=active"
  | { ok: false; reason: string; remediation?: string };
```

Rules:

- `execute` calls the **existing service layer / API**, with the same validation
  a real user hits. Never bypass into the ORM or raw SQL.
- `execute` receives `idempotencyKey = sha256(run_id + step_id + canonical(input))`
  and the service layer must honour it. If idempotency support does not exist
  yet, add it as part of Phase 1.
- `verify` is the sole authority on success. The LLM never decides pass/fail.
- `evidence` is a short human-readable string surfaced in the UI, so the
  operator can see *why* we believe the step worked.

## 4. Persistence

```
onboarding_runs
  id, tenant_id (nullable until created), status, created_by,
  started_at, completed_at, context jsonb

onboarding_step_states
  run_id, step_id,
  status: blocked | ready | collecting | executing | verified | failed | skipped
  input jsonb, output jsonb,
  verify_evidence text, error text,
  attempts int, updated_at

onboarding_audit_log
  run_id, step_id, actor (human_id | 'copilot'), action,
  request jsonb, response jsonb, at
```

`context` accumulates ids as the run progresses (`tenantId`, `ownerId`,
`restaurantId`, `branchId`, `tableIds`, ...) and is the input to `autofill`.

A background reconciler recomputes `blocked` → `ready` whenever a step reaches
`verified`. Status is derived from the graph, never set ad hoc.

## 5. Bulk ingestion (the part that actually saves days)

Tenant setup takes ninety seconds; menu and inventory take three days. Build
these as first-class importers, not chat.

**Menu import**
- Accept PDF, image, XLSX/CSV, or plain pasted text.
- Extract to `{ category, name, description, price, isVeg, gstRate, confidence }[]`.
- Render a **review grid** — sortable table, inline edit, bulk actions,
  low-confidence rows flagged. Not a chat transcript.
- Commit in one transaction after operator approval.

**Inventory + recipes**
- Derive a candidate ingredient list from menu item names.
- Propose recipe mappings (dish → ingredients + quantities) for the operator to
  *correct*, never to author from scratch.
- Everything proposed is marked `source: 'ai_suggested'` until confirmed.

**Staff import**
- Accept pasted freeform text (WhatsApp-style name/phone lists) or CSV.
- Parse to `{ name, phone, role }[]`, dedupe, bulk create, dispatch credentials
  over SMS/email. Never display raw passwords in chat history.

**Tables + QR**
- Single question: table count and optional section names.
- Bulk create, generate QR codes, emit a print-ready PDF sheet.

## 6. Smoke test gate

Implement as a deterministic script (not LLM-driven) that runs against the live
tenant with every created record flagged `is_onboarding_test = true`:

1. Place an order on a real table via the customer-facing path.
2. Assert it appears on the KDS with correct items.
3. Transition it through the real kitchen states to ready.
4. Generate the bill; assert subtotal, CGST, SGST and total are arithmetically
   correct to the paisa, and that the GST split matches the configured rates.
5. Run a payment in sandbox mode; assert settlement state.
6. Hard-delete all `is_onboarding_test` rows.
7. Re-query and assert the tenant contains zero test artifacts.

If any assertion fails, the run status becomes `blocked_at_smoke_test` with the
failing assertion surfaced verbatim. Handover is impossible until it passes.

## 7. Handover pack

On smoke test pass, generate and email:

- Owner + manager credentials (one-time links, not plaintext passwords)
- Staff roster with roles and login method
- QR code sheet as print-ready PDF
- Config summary: currency, tax rates, table count, menu item count, branch details
- Two-page quick-start guide

Mark the run `completed` and record `time_to_live_tenant` as the headline metric.

## 8. The LLM driver (build last, keep thin)

A loop that receives serialized run state each turn and calls tools.

**Tools exposed:** one `execute_<step_id>` and one `verify_<step_id>` per step,
plus `get_run_state`, `ask_operator(question, schema)`, and the importers.

**The model is responsible for:** parsing messy human input into step schemas,
asking only for genuinely missing fields, explaining API errors in plain
language, and choosing which `ready` step to tackle next.

**The model is explicitly NOT responsible for:** deciding whether a step
succeeded, inventing tax rates or prices, writing to the database, or skipping
the smoke test. These are enforced in code, not in the system prompt.

Every tool call is written to `onboarding_audit_log` with actor `'copilot'`.

## 9. Non-negotiables

- No raw SQL or ORM writes from co-pilot code. Service layer only.
- No step marked verified without a `verify()` returning `ok: true`.
- No secrets, passwords, or API keys in LLM context or chat history.
- The whole system must work with the LLM disabled — the registry drives a
  plain deterministic wizard as well. The co-pilot is a driver, not a dependency.
- Tenant isolation asserted in tests: a run for tenant A must be unable to
  read or write tenant B.

---

# Phase prompts

Run these one at a time in Claude Code. Review and commit between each.

### Phase 0 — Explore and plan

```
Read docs/ONBOARDING_COPILOT_SPEC.md.

Then explore this codebase and report back before writing any code:
- Where the tenant, restaurant, branch, table, staff, menu, inventory and
  recipe services live, and what their public interfaces look like.
- Whether the API supports idempotency keys today, and if not, the smallest
  change that would add it.
- How auth and tenant scoping work, and how a scoped onboarding token could
  be issued.
- Existing test setup and how to run it.

Then propose a file-by-file implementation plan for Phase 1 only.
Do not write code yet. Ask me about anything ambiguous.
```

### Phase 1 — Step registry and run state

```
Implement Phase 1 from the spec: the step registry, persistence tables and
the state machine. Specifically:

- The OnboardingStep interface exactly as specified in section 3.
- Migrations for the three tables in section 4.
- All steps in the dependency graph in section 2, each with collect schema,
  autofill, execute, verify and undo. execute must call existing services.
- The reconciler that derives blocked/ready from the graph.
- Idempotency key generation and plumbing.

Include unit tests for the graph reconciler (including the parallel tracks and
the recipes-needs-menu-and-inventory join) and integration tests proving each
step's verify actually fails when the underlying record is missing.

No UI and no LLM in this phase.
```

### Phase 2 — Deterministic wizard UI

```
Build the operator UI driven entirely off the step registry — it must render
correctly for any registry change without UI edits.

- Graph view showing all steps with status, parallel tracks side by side.
- Auto-generated forms from each step's Zod collect schema, prefilled from autofill.
- Verify evidence shown inline on each completed step.
- Resume: reopening a run lands on the first ready step.
- Failure states show the verify reason and remediation, with a retry action.
```

### Phase 3 — Bulk importers

```
Implement the importers in section 5: menu, inventory + recipes, staff, tables + QR.

Each importer is: parse → review grid → commit in one transaction.
Low-confidence rows must be visually flagged. AI-suggested records are marked
source='ai_suggested' until an operator confirms them.

The menu importer must accept PDF, image, XLSX/CSV and pasted text.
The QR generator must emit a print-ready PDF sheet.
```

### Phase 4 — Smoke test gate

```
Implement the smoke test from section 6 as a deterministic script with explicit
assertions. Every record it creates is flagged is_onboarding_test.

Critical: assert the CGST/SGST split and totals are correct to the paisa, and
that cleanup leaves zero test artifacts. Handover must be structurally
impossible while the gate is failing — enforce this in the state machine, not
just the UI.
```

### Phase 5 — LLM driver

```
Add the co-pilot driver from section 8 on top of the existing registry.

Expose execute/verify per step as tools plus the importers and ask_operator.
Serialize run state into the system prompt each turn. Log every tool call to
onboarding_audit_log with actor 'copilot'.

The model must not be able to mark a step verified, skip the smoke test, or
write to the database directly — enforce all three in code. Add tests that
attempt each of those three violations and assert they fail.

The deterministic wizard from Phase 2 must continue to work with the LLM disabled.
```
