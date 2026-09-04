# RestaurantOS Setup Copilot — Phase 1 Design

Status: **DRAFT — awaiting approval.** No implementation code has been written.

Scope: the seven items requested — persistence tables, the `OnboardingStep`
contract/registry/reconciler, resumable/idempotent orchestration, atomic
first-owner provisioning, the co-pilot's identity, `Idempotency-Key` on the
two remaining routers, and correct intra-track step ordering. Bulk
importers, the smoke-test gate, the LLM driver, and the wizard frontend are
explicitly deferred (Phases 2–5) and are not designed here.

---

## 0. Status

All four flags from the first draft were reviewed and resolved by amendment.
This section now records the decisions; the rest of the document reflects
them throughout — there is no separate "changed since v1" appendix, the
body text below *is* the current design.

1. **Resolved: `create_owner` deleted, `create_tenant` renamed
   `provision_tenant`.** No longer two StepIds in tension — one step, whose
   `verify()` asserts everything both used to check. See §A.4.
2. **Resolved: `configure_currency` deleted**, folded into
   `provision_tenant`'s `collect` schema and `verify()`. `configure_tax`
   was checked against the same question and is confirmed to stay a real
   step — `CreateTaxUseCase` is genuinely create-only (no
   `update_tax.py`/`delete_tax.py` anywhere in `modules/operations`). See
   §A.7.
3. **Resolved: item 5 deferred, not reopened.** Recorded under "Deferred —
   decided" in §A.5, with the Phase 2 wizard named as the specific trigger
   that ends the deferral. `onboarding_audit_log` still gets `actor_type`
   and `actor_id` from day one regardless of the deferral — see §A.1 and
   §A.3.
4. **Resolved: RLS exemption approved**, with a `CHECK` and a trigger added
   to close the one integrity gap an RLS-exempt table would otherwise have
   — see §A.1. `require_platform_admin` enforcement confirmed at the router
   level (not just documented) — see §C.
5. **New this round: `backfill_tenant_owner.py` gets a same-tenant guard
   and a retitled docstring; the §D audit query is a recurring check, not a
   one-time migration step.** See §A.4 and §D.

---

## A. Proposed design

### A.1 Persistence — `onboarding_runs`, `onboarding_step_states`, `onboarding_audit_log`

**Access model, decided first because it drives the schema:** none of these
three tables get Postgres RLS or a `NOT NULL tenant_id` FK. They are
platform-level tables, gated by `require_platform_admin` at the route/use-case
layer — exactly the precedent already set by `tenants` itself
(`tenant_provisioning_service.py`'s own comment: "the `tenants` row...
carries no RLS policy of its own — Data Architecture v2.0 §5.2") and by
`platform_idempotency_keys` (0013's own migration docstring, same reasoning).
Reason: `onboarding_runs.tenant_id` is genuinely unknown before
`provision_tenant` verifies, and the graph-view requirement (spec §2: seed
every step as `blocked` up front so the UI can render the whole graph
immediately) means `onboarding_step_states` rows for `create_restaurant`,
`create_branch`, etc. must exist *before* a tenant does too. A
`tenant_id IS NULL OR tenant_id = current_setting(...)` RLS policy would
technically work but is a pattern this codebase has never used anywhere,
and it would let any tenant's session see every not-yet-tenanted run
system-wide (harmless, since those rows carry no tenant identity to leak,
but still a new kind of policy to reason about for no real benefit over
just not having RLS here). Simpler and consistent: no RLS, platform-admin
gate.

```
onboarding_runs
  id                  str (ULID, PK)
  tenant_id           str | None   -- FK -> tenants.id, nullable, set once provision_tenant verifies
  status              OnboardingRunStatus  -- in_progress | blocked | completed | abandoned
  created_by_user_id  str          -- the platform-admin who started the run (never null — always a real actor)
  context             JSONB        -- accumulated ids: tenantId, ownerId, restaurantId, branchId, tableIds, ...
  started_at          datetime
  completed_at        datetime | None

onboarding_step_states
  id                  str (ULID, PK)
  run_id              str          -- FK -> onboarding_runs.id, NOT NULL
  step_id             StepId       -- validated against the registry's known ids, not a free string
  status              StepStatus   -- blocked | ready | collecting | executing | verified | failed | skipped
  input               JSONB | None
  output              JSONB | None
  idempotency_key     str | None   -- computed key, stored for observability only (§A.3 — not the enforcement mechanism)
  verify_evidence     str | None
  error                str | None
  attempts            int (default 0)
  updated_at          datetime
  UNIQUE(run_id, step_id)

onboarding_audit_log
  id                  str (ULID, PK)
  run_id              str          -- FK -> onboarding_runs.id, NOT NULL
  step_id             StepId | None  -- null for run-level events (started, abandoned)
  actor_type          ActorType    -- 'human' | 'copilot' — populated from day one, independent of §A.5's deferral
  actor_id            str | None   -- the acting user's id
  action               str          -- "collect_input" | "execute" | "verify" | "undo"
  request              JSONB
  response             JSONB
  at                   datetime     -- append-only, no updated_at
```

One deliberate deviation from spec §4's literal schema: `actor
(human_id | 'copilot')` is split into `actor_type` + `actor_id` instead of
one overloaded string column. `'copilot'` is not a real user id, and mixing
the two invites exactly the kind of bug where an audit query joins `actor`
against `users.id` and silently drops every copilot row.

**`actor_type` vs. `actor_id` in Phase 1, concretely** (this is the part
that needed spelling out, per your amendment): every orchestrator-initiated
write sets `actor_type='copilot'`. `actor_id` is **not** null for these
rows in Phase 1 — there is no copilot service-user yet (§A.5), so
`actor_id` holds `ctx.owner_id`, the real identity whose authority the
orchestrator is actually using (e.g. as `granter_user_id` when calling
`AssignUserRoleUseCase`). The two columns answer different questions on
purpose: `actor_type='copilot'` says "this write was orchestrator-driven,
not a human clicking through the wizard"; `actor_id` says "and this is the
authority it acted under." When Phase 2 introduces a real copilot
service-user, `actor_id` starts holding *that* user's id instead of the
owner's — `actor_type='copilot'` stays true across the transition, so
anything querying by `actor_type` doesn't need to change when Phase 2
ships. `actor_id` stays nullable in the schema for the rare row with no
acting identity at all (e.g. a pure reconciler bookkeeping event); it is
not nullable in practice for any row Phase 1 actually writes.

**Integrity safeguard for the RLS exemption.** `onboarding_runs` has no
RLS, so it loses the usual database-level guarantee that a row's tenant
never silently changes out from under it. Two constraints close that gap
without needing RLS:

```sql
ALTER TABLE onboarding_runs ADD CONSTRAINT ck_onboarding_runs_completed_has_tenant
    CHECK (status <> 'completed' OR tenant_id IS NOT NULL);

CREATE FUNCTION onboarding_runs_tenant_id_immutable() RETURNS trigger AS $$
BEGIN
    IF OLD.tenant_id IS NOT NULL AND NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
        RAISE EXCEPTION 'onboarding_runs.tenant_id is immutable once set (run %)', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_onboarding_runs_tenant_id_immutable
    BEFORE UPDATE ON onboarding_runs
    FOR EACH ROW EXECUTE FUNCTION onboarding_runs_tenant_id_immutable();
```

The `CHECK` is a single-row invariant ("a run cannot be `completed` while
still tenant-less") and needs no trigger. The immutability rule
("`tenant_id`, once set, can never become a *different* non-null value")
is a transition invariant — it has to compare `OLD` against `NEW`, which a
`CHECK` constraint cannot do, so it needs a `BEFORE UPDATE` trigger. This
is a narrower, lower-risk shape than the "≥1 owner grant per tenant"
invariant in §D, which I'm still not proposing a trigger for — that would
need cross-table aggregation (counting `user_roles` rows joined through
`roles`) inside trigger logic, a meaningfully heavier and more fragile
thing to get right than a single-column monotonic-once-set check on the
row's own `OLD`/`NEW` values.

No FK from `onboarding_step_states.step_id` to a "steps" table — there
isn't one. The registry (§A.2) is the source of truth for the graph, same
as spec §3 intends; `step_id` is validated at the Pydantic/application
layer against the registry's known `StepId` values.

### A.2 The `OnboardingStep` contract, registry, reconciler

Spec §3's TypeScript/Zod interface translated into this codebase's idiom:

- **`Protocol`, not `ABC`.** This codebase already uses `Protocol` for
  every port with multiple implementations (`UserRepository`,
  `TenantRepository`, etc., all in `domain/ports/`) and uses `ABC` nowhere
  I found. `OnboardingStep` follows the established pattern.
- **`collect: ZodSchema<TInput>` → `collect_schema: type[TInput]`.**
  Pydantic *is* the schema-as-a-type mechanism already; there's no
  separate "schema instance" object the way Zod has one.
- **`VerifyResult`'s TS discriminated union → a Pydantic discriminated
  union**, not one model with nullable fields — the `Literal[True]` /
  `Literal[False]` tag makes "evidence required on success, reason
  required on failure" a type-level fact instead of an implicit
  convention:

```python
class VerifySuccess(BaseModel):
    ok: Literal[True] = True
    evidence: str

class VerifyFailure(BaseModel):
    ok: Literal[False] = False
    reason: str
    remediation: str | None = None

VerifyResult = VerifySuccess | VerifyFailure
```

- **`RunContext`** is a typed Pydantic model (`OnboardingRunContext`), not
  a loose dict — `tenant_id`, `owner_id`, `restaurant_id`, `branch_id`,
  `table_ids`, etc., all `str | None`. The DB column (`onboarding_runs
  .context`) is the JSONB *storage* shape; `OnboardingRunContext` is what
  gets constructed from it and handed to steps at runtime. This split
  matters because steps should never see a bag of `Any`.

```python
class OnboardingStep(Protocol[TInput, TOutput]):
    id: StepId
    title: str
    requires: tuple[StepId, ...]
    collect_schema: type[TInput]
    autonomous: bool

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]: ...
    async def execute(self, input: TInput, ctx: OnboardingRunContext) -> TOutput: ...
    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult: ...
    async def undo(self, ctx: OnboardingRunContext) -> None: ...
```

Every concrete step (e.g. `CreateRestaurantStep`) is a small class built
via DI exactly like a use case (`__init__(self, *, create_restaurant_use_case, get_restaurant_use_case)`).
`execute()` adapts `TInput` + `ctx` into the real use case's request DTO
and calls it — this *is* "reuse the existing service layer," not a
principle bolted on afterward. `verify()` calls the corresponding
`Get*UseCase`/`List*UseCase` to read the record back:

```python
class CreateRestaurantStep:
    def __init__(self, *, create_restaurant_use_case, get_restaurant_use_case):
        ...

    async def execute(self, input: CreateRestaurantStepInput, ctx: OnboardingRunContext) -> RestaurantDTO:
        return await self._create_restaurant_use_case.execute(
            ctx.tenant_id, CreateRestaurantRequestDTO(legal_name=input.legal_name, ...)
        )

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        restaurant = await self._get_restaurant_use_case.execute(ctx.tenant_id, ctx.restaurant_id)
        if restaurant is None:
            return VerifyFailure(reason=f"restaurant {ctx.restaurant_id} not found on read-back")
        return VerifySuccess(evidence=f"GET restaurant {restaurant.id} -> status={restaurant.status}")
```

**Registry.** A plain in-memory structure (`OnboardingStepRegistry`,
wrapping `dict[StepId, OnboardingStep]`), constructed once via DI in
`presentation/dependencies.py` — not a database table. The graph
(`requires`) lives in code, same as every step's own class. Two helpers:
`topological_order()` and `direct_dependents(step_id)`.

**Reconciler.** A pure function, same style as `RoleGrantPolicy`
(stateless domain logic, no I/O):

```python
def recompute_ready_steps(
    step_states: dict[StepId, StepStatus], registry: OnboardingStepRegistry
) -> dict[StepId, StepStatus]:
    """For every step currently `blocked`, promote to `ready` iff every
    entry in `requires` is `verified`. Pure — the caller persists the diff."""
```

Spec §4 calls this "a background reconciler." **There is no background
process anywhere in this codebase** (no scheduler, no queue — even
`backfill_tenant_owner.py`'s own docstring states this as a deliberate
property: "no scheduler, migration hook, or app-startup call... anywhere
in this codebase"). Phase 1 has no autonomous actor to run one for yet
(no LLM driver). So the reconciler runs *synchronously*, in the same
transaction, immediately after a step's `verify()` returns `ok=True` —
behaviorally equivalent for a system where nothing calls steps except a
human or a test, and it's what Phase 5's LLM driver will call in its own
loop later.

### A.3 Resumable, idempotent orchestration

`OnboardingOrchestrator` (application layer):

```python
class OnboardingOrchestrator:
    async def start_run(self, *, created_by_user_id: str) -> OnboardingRunDTO: ...
    async def get_run_state(self, run_id: str) -> OnboardingRunStateDTO: ...
    async def collect_and_execute(self, run_id: str, step_id: StepId, raw_input: dict) -> StepExecutionResultDTO: ...
```

`collect_and_execute` flow:

1. Load the run + all step states. Reject if `step_id` is not currently
   `ready` (defense in depth — don't trust the caller to only offer ready
   steps, same "belt and suspenders" habit this codebase applies
   everywhere else).
2. `step.autofill(ctx)` supplies defaults, then `raw_input` is validated
   against `step.collect_schema` (Pydantic).
3. **Idempotency key = `f"{run_id}:{step_id}:{fingerprint_request(validated_input.model_dump(mode='json'))}"`**
   — reusing `platform/idempotency/fingerprint.py::fingerprint_request`
   exactly, the existing SHA-256-of-sorted-JSON helper. This *is* spec
   §3's `sha256(run_id + step_id + canonical(input))`; no new hashing code.
4. Transition the step to `executing`, increment `attempts`, persist —
   **before** calling `execute()`. This is the resumability anchor: if the
   process dies mid-execute, the step is left visibly `executing`, not
   silently lost.
5. Call `execute()` through the **existing** `IdempotencyGuard.run(...)`
   (`platform/idempotency/guard.py`) — the exact claim-then-execute-then-
   record protocol the 15 HTTP routers already use, just invoked from the
   orchestrator instead of a route handler. The wrapped callable shapes
   the step's domain exceptions into `(status, body)` the same way
   `core/exceptions.py::build_error_response` already does for routers,
   and returns `(200, {"output": jsonable(output)})` on success. **One
   exception:** the `provision_tenant` step has no `tenant_id` yet when
   this runs — same bootstrapping problem `PlatformIdempotencyGuard`
   already solves for `POST /api/v1/admin/tenants`. The orchestrator
   branches: for `provision_tenant` specifically, wrap through
   `PlatformIdempotencyGuard` instead. Every other step uses the normal
   tenant-scoped
   `IdempotencyGuard`. No new idempotency infrastructure — this reuses
   both existing guards, unchanged.
6. On success: persist `output`, call `step.verify(ctx)`. **`verify` is
   the sole authority — a successful `execute()` with a failing `verify()`
   is `failed`, not `verified`.** On `ok=True`: update `ctx` with any new
   ids, persist, run the reconciler, unblock dependents.
7. Write one `onboarding_audit_log` row per attempt — always, success or
   failure.

**Resume behavior**, satisfying spec §1.4 ("resume cleanly at any point,
without duplicating records"): on `get_run_state()`, any step found stuck
in `executing` is **not** blindly re-executed. The orchestrator calls that
step's `verify()` first — the previous `execute()` may well have succeeded
before the crash. Only if `verify()` fails does a retry re-enter
`collect_and_execute`, at which point the stored idempotency key is the
safety net if the underlying use case was in fact already applied.

### A.4 `provision_tenant` — the tenant, its Owner, and its activation token, atomically

One step, not two. `create_owner` is deleted from the graph; `create_tenant`
is renamed `provision_tenant`, and its `collect` schema now includes the
owner's contact fields and the currency default (folding in the deleted
`configure_currency` — see §A.7). Its `verify()` is the one place that
proves the whole atomic write actually landed, not just the tenant row.

`TenantProvisioningService.provision()` (`tenant_provisioning_service.py:337`)
already returns `dict[str, Role]` from `seed_default_roles(...)` at line
408 — `roles_by_name["Tenant Owner"]` is available immediately after that
call, inside the same transaction. Extension:

```python
async def provision(
    self, *, legal_name: str, display_name: str, default_currency_code: str,
    owner_email: str, owner_phone: str | None = None,
) -> tuple[Tenant, User, str]:   # str = raw one-time activation token, never persisted
    ...
    roles_by_name = await seed_default_roles(...)
    owner_role = roles_by_name["Tenant Owner"]

    owner = User(
        id=generate_ulid(), tenant_id=tenant_id, email=owner_email, phone=owner_phone,
        password_hash=None, pin_hash=None, permission_version=1,
        status=UserStatus.INVITED, created_at=now, is_platform_admin=False,
    )
    owner = await user_repo.create(owner)

    await user_role_repo.create(UserRole(
        id=generate_ulid(), tenant_id=tenant_id, user_id=owner.id, role_id=owner_role.id,
        branch_id=None, granted_at=now, granted_by_user_id=None,   # <- no delegating actor, by design
    ))
    # RoleGrantPolicy.ensure_can_grant is NOT called. Architecturally identical
    # to what backfill_tenant_owner.py already does, for the same stated reason:
    # a zero-role tenant has no roles.assign holder to check the grant against.

    raw_token = secrets.token_urlsafe(32)
    await activation_token_repo.create(OwnerActivationToken(
        id=generate_ulid(), tenant_id=tenant_id, user_id=owner.id,
        token_hash=hash_token(raw_token), issued_at=now,
        expires_at=now + timedelta(hours=_ACTIVATION_TTL_HOURS), used_at=None,
    ))

    await outbox.publish(tenant_id, UserCreated(
        user_id=owner.id, tenant_id=tenant_id, email=owner.email,
        created_by_user_id=None,   # <- see file-change list, §B: one field goes str -> str | None
        occurred_at=now,
    ))
    ...
    return tenant, owner, raw_token
```

`User.password_hash: str | None` and `UserStatus.INVITED` **already
exist** in `domain/entities/user.py` — `INVITED` is currently an unused
enum value with no code path that sets it anywhere. `UserRole
.granted_by_user_id: str | None` is **already nullable**. `ensure_can_authenticate()`
already rejects non-`ACTIVE` users at login, so an `INVITED` owner
correctly cannot log in with a password that doesn't exist yet — zero
changes needed there. The raw activation token is returned exactly once,
in the response, mirroring the existing convention in `UserDTO
.generated_password: str | None` (Gap 1) — never logged, never stored
except as a hash, modeled on `Session.refresh_token_hash`'s
only-a-hash-is-durable pattern.

**`ProvisionTenantStep`'s `verify()`** is where the four assertions you
asked for actually live — `execute()` succeeding only proves the writes
were attempted, not that the tenant is in a state the rest of the graph
can safely build on:

```python
class ProvisionTenantStep:
    async def execute(self, input: ProvisionTenantStepInput, ctx: OnboardingRunContext) -> ProvisionTenantOutput:
        tenant, owner, raw_token = await self._provisioning_service.provision(
            legal_name=input.legal_name, display_name=input.display_name,
            default_currency_code=input.default_currency_code,   # autofilled INR for country IN — folded-in configure_currency, §A.7
            owner_email=input.owner_email, owner_phone=input.owner_phone,
        )
        return ProvisionTenantOutput(tenant_id=tenant.id, owner_id=owner.id, activation_token=raw_token)

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        tenant = await self._get_tenant_use_case.execute(ctx.tenant_id)                       # exists
        if tenant is None or tenant.status != "active":
            return VerifyFailure(reason=f"tenant {ctx.tenant_id} not active on read-back")
        if tenant.default_currency_code != ctx.expected_currency_code:
            return VerifyFailure(reason="tenant currency does not match what was requested/autofilled")

        owner = await self._get_user_use_case.execute(ctx.tenant_id, ctx.owner_id)            # NEW, small — see below
        if owner is None or owner.status != "invited":
            return VerifyFailure(reason=f"owner user {ctx.owner_id} missing or wrong status")

        owner_permissions = await self._resolve_user_permissions_use_case.execute(            # exists — reused, not a role-name lookup
            ctx.tenant_id, ctx.owner_id
        )
        if "roles.assign" not in owner_permissions.permission_codes:
            return VerifyFailure(reason="owner user has no roles.assign — Tenant Owner grant missing or wrong")

        token_active = await self._get_owner_activation_token_status_use_case.execute(        # NEW, small — see below
            ctx.tenant_id, ctx.owner_id
        )
        if not token_active:
            return VerifyFailure(reason="no unexpired, unused activation token for owner")

        return VerifySuccess(evidence=(
            f"tenant {ctx.tenant_id} active (currency {tenant.default_currency_code}); "
            f"owner {ctx.owner_id} invited with roles.assign; activation token unexpired"
        ))
```

Two small reads don't exist yet and need to be added — flagging both
rather than quietly assuming them:

- **`GetUserUseCase`** — there is no single-user read anywhere in
  `modules/identity` today (`list_users.py` lists all of a tenant's users;
  nothing takes a `user_id` and returns one). A thin, obviously-reusable
  addition, same shape as `GetRestaurantUseCase`/`GetBranchUseCase`.
- **`GetOwnerActivationTokenStatusUseCase`** — reads the just-created
  `owner_activation_tokens` row back (unexpired, unused). New because the
  table itself is new; same `Get*UseCase` convention.

Checking `"roles.assign" in owner_permissions.permission_codes` via the
**existing** `ResolveUserPermissionsUseCase` (already used by
`assign_user_role.py` to resolve a granter's authority) does double duty:
it proves the Owner role grant exists *and* that it actually carries
`roles.assign` — a direct answer to "does roles.assign have a holder,"
for the one user who could possibly hold it immediately after
provisioning. It's a more precise check than looking up the role by name
("Tenant Owner"), which would pass even if a future change quietly
stopped granting that role `roles.assign`.

**New use case: `ActivateOwnerUseCase`.** Genuinely new — nothing in the
codebase lets a user set their own first password from an out-of-band
token today. Takes `(raw_token, new_password)`: hashes the token via
`TokenService.hash_refresh_token` (reused as-is — the interface already
documents *why* it's a fast SHA-256 digest rather than Argon2id: "a
refresh token is already a high-entropy random value, not a low-entropy
human-chosen secret," which describes an activation token exactly as well
as a refresh token; adding a second, near-identical hashing method to the
same port for the same reason would be the kind of duplication this
design is trying to avoid elsewhere), looks up the row, checks
`used_at is None` and not expired, sets `password_hash` via the existing
`PasswordHasher` port, flips `status` `INVITED -> ACTIVE`, marks the token
used. This is an identity-module addition (small, in the same family as
Gap 1's `CreateUserUseCase`), not "onboarding orchestration code" — the
non-negotiable about reusing existing use cases applies to the
orchestrator, and this is exactly the kind of small identity-module
primitive the orchestrator is then allowed to reuse.

**Confirmed in scope, per your amendment: identical failure response for
unknown / expired / already-consumed tokens, plus rate limiting.** This
endpoint is unauthenticated and the token *is* the credential — exactly
the shape `qr_resolution_router.py`/`guest_order_router.py` already
established a pattern for (their own docstring names it directly:
"enumeration protection... so a scanning client can't distinguish
[case A] from [case B] by response shape"). Reused here, not reinvented:

- **One exception, one response, regardless of which of the three
  conditions failed.** `ActivateOwnerUseCase` raises a single
  `OwnerActivationTokenInvalidError` whether the token hash matches no
  row at all, matches an expired row, or matches an already-used row —
  the use case does not expose *which* of the three happened to its
  caller, so the router has nothing differentiated to leak even if it
  wanted to. One error code, one HTTP status (`400`), one JSON body,
  reused byte-for-byte — the same discipline `_NOT_FOUND_BODY`/
  `_RATE_LIMITED_BODY` already apply in `guest_order_router.py`. (This
  supersedes the two-error, 400/410 split the first draft of this
  section proposed — that split is exactly the oracle your amendment is
  closing.)
- **No timing side-channel to close beyond that.** `LoginUserUseCase`
  needs the dummy-hash-verify trick (`_DUMMY_PASSWORD_HASH`) because a
  real Argon2id verify is slow enough to be a distinguishable timing
  signal against an early-exit "no such user" path. Token lookup here has
  no equivalent slow step — all three failure conditions are reached only
  *after* the same SHA-256 lookup by hash, then a cheap `used_at`/`expires_at`
  comparison, so the three paths already cost about the same. No dummy-hash
  trick needed; noting why, rather than silently omitting a pattern the
  codebase uses elsewhere for a reason that happens not to apply here.
- **Rate limiting**, reusing `platform/rate_limiting`'s existing
  fixed-window-counter mechanism and `RateLimitCounterModel` table exactly
  as `GuestOrderRateLimiter` does (no migration — that table's
  `bucket_type` CHECK already allows `'ip'`/`'token'`, both of which apply
  here unchanged). A small new `OwnerActivationRateLimiter`, same shape,
  keyed by source IP and by the token itself, both buckets prefixed
  (`activation:`) the same way `GuestOrderRateLimiter` prefixes
  `order:` to keep its counters in a separate namespace from
  `QRResolutionRateLimiter`'s unprefixed ones on the same table.

Delivering the raw token to the actual client (email, SMS, printed sheet)
is explicitly the handover pack (§7 of the spec) — out of scope here.
Phase 1 makes the
token exist and be exchangeable; it does not deliver it anywhere.

**The invariant:** *a tenant with zero `roles.assign` holders cannot bootstrap
a new grant through any existing API* — confirmed in the prior exploration
report and unchanged by this design. Before this change, every tenant had
this property between `provision()` returning and someone running
`backfill_tenant_owner.py --apply`. After this change, no tenant provisioned
through the fixed `provision()` path is ever in that state, even
momentarily — the Owner grant is in the same transaction as the tenant row
itself, so `provision()` either produces a fully-owned tenant or nothing
commits at all.

**Can `scripts/backfill_tenant_owner.py` be deleted? No — and this is not
a hedge.** Two independent reasons it stays:

1. Every tenant provisioned *before* this migration ships still has zero
   owner grants and needs this exact script to fix (see §D — this cannot
   be done as a blind automatic migration).
2. **Phase 1 only guarantees the invariant at creation time, not for all
   time.** Nothing here stops a tenant from *degrading* back to zero
   `roles.assign` holders later — an Owner's role grant gets revoked by a
   bug, a mistaken admin action, or every Owner account gets deactivated.
   That failure mode is identical to the one `backfill_tenant_owner.py`
   already exists to fix, and Phase 1 adds no new safeguard against it
   recurring post-creation. Deleting the script would leave manual SQL as
   the only recovery path for that scenario — a regression, not cleanup.

**What changes, concretely:**

1. **Docstring retitle.** Stop framing itself as "for tenants that predate
   the RBAC Foundation" (that reason mostly goes away once §D's audit
   query has been acted on for every tenant it currently flags) and start
   framing itself as the general operator recovery tool for any tenant
   that has degraded to zero `roles.assign` holders, whatever the cause —
   pre-Phase-1 legacy tenant or a Phase-1-provisioned tenant whose Owner
   was later deactivated or revoked.
2. **New guard: refuse loudly if the target tenant already has an Owner
   grant.** Before Phase 1, this script only ever ran against tenants that
   were zero-role *by construction* (nothing else could grant a role on
   them), so no such check existed. After Phase 1, most tenants it could
   be pointed at *do* already have an owner, and running it against one by
   mistake (wrong `--tenant-id`, stale runbook) should be a loud,
   immediate refusal, not a silent double-grant:

   ```python
   existing_owner = await user_role_repo.get_by_role_name(tenant_id, "Tenant Owner")
   if existing_owner is not None:
       raise SystemExit(
           f"Tenant {tenant_id} already has a Tenant Owner grant "
           f"(user {existing_owner.user_id}, granted {existing_owner.granted_at}). "
           "Refusing to run — this script is for tenants with zero roles.assign "
           "holders only. If that user's access needs fixing, use the RBAC API, "
           "not this script."
       )
   ```

   This check runs even without `--apply` (dry-run should report the same
   refusal, not a false "would grant" preview).

It stays out of the copilot's own code path, as instructed — `provision_tenant`
never calls it and never will; it is exclusively an operator-run script.

### A.5 The co-pilot's identity — Deferred, decided

This is a decision record, not an open question. The model is chosen now;
building it is deferred to whichever phase first needs it. Re-litigating
this in that phase is out of scope for that phase too — see the closing
paragraph below.

**Decision: your working assumption (per-run service user, real row in
`users`/`user_roles`), with two refinements — not a purpose-built scoped
token.**

Why the service-user approach wins, concretely, not just in principle:

- **RLS is free.** `UnitOfWork` sets `app.tenant_id` from a plain
  `tenant_id` string; a real user's `tenant_id` satisfies that with zero
  new code.
- **RBAC is free.** `require_permission_at_any_scope` and
  `RoleGrantPolicy` operate on whatever role a real `UserRole` row grants
  — an Owner-equivalent role for the copilot's user passes every existing
  check unchanged.
- **Revocation is free and already tested.** `RevokeUserRoleUseCase`
  already bumps `permission_version` (`revoke_user_role.py:70`), which is
  this codebase's existing, proven mechanism for immediately invalidating
  a user's live sessions. "Revoked at handover" is a call to an existing
  use case, not new code.

Why a purpose-built scoped token loses: it would need its own claim/`aud`
type, its own middleware to recognize and validate that type distinctly
from a normal session, its own revocation path (`permission_version` is
keyed to a real `user_id` — a token type wouldn't have one), and it would
**not** get RLS for free (`TenantContext` today is always derived from an
`AuthenticatedPrincipalDTO`, itself always derived from a real logged-in
user). That's a meaningful amount of new, security-sensitive surface to
build and test, to re-derive a capability the service-user design already
has. Per your own instruction, I can't show the service-user approach
fails, so I'm not proposing the alternative.

**Two refinements to your assumption, both because the literal fields you
described don't have a home in the existing schema:**

1. **No stored `expires_at` on the grant.** Neither `User` nor `UserRole`
   has an expiry column — `UserRole`'s own docstring states revocation is
   soft-delete, explicit, at the repository layer, with "no revoke() method
   on the entity" because the pattern is always an explicit action, never a
   passive expiry check. Nothing else in this codebase authorizes via a
   stored expiry (`Session.expires_at` is for refresh-token liveness, a
   different concern). Simpler and more consistent: the orchestrator calls
   the existing `RevokeUserRoleUseCase` explicitly at handover. No schema
   change.
2. **No `actor_type` column on `users`.** "Is this a copilot" never needs
   to be derivable from the `users` row itself — nothing in RLS, RBAC, or
   permission-checking code needs to know. It only needs to appear in
   `onboarding_audit_log.actor_type` (§A.1), which is a pure
   orchestration-layer concern. Adding a permanent column to a core
   identity table for a Phase-1-scoped concept is exactly the kind of
   change that outlives its reason.

**Deferred — decided.** I traced whether the orchestrator actually needs
this identity to do its Phase 1 job, and it doesn't.
`AssignUserRoleUseCase.execute()` needs a real `granter_user_id` that
holds `roles.assign` — but the orchestrator already has one, for free,
sitting in `ctx.owner_id` (the atomically-created Owner from §A.4). No use
case in this codebase takes a token or a principal; permission checks live
at the HTTP router layer, and nothing calls the orchestrator over HTTP in
Phase 1.

**The trigger that ends the deferral is specific, not vague: the first
HTTP-reachable caller of the orchestrator — concretely, the Phase 2
wizard.** That is the first point at which "who is this request
authenticated as" becomes a real question instead of a hypothetical one.
When Phase 2 reaches that point, it implements the recommendation above
**as written** — per-run service user, no stored expiry (explicit
`RevokeUserRoleUseCase` call instead), no `actor_type` column on `users`.
Phase 2 does not re-evaluate service-user-vs-scoped-token; that evaluation
was done here, with the codebase evidence to back it, and re-running it
without new evidence would just be re-asking a question that's already
answered. If something concrete changes between now and Phase 2 that
actually bears on the answer (not just "it's been a while, let's double
check"), that's worth a fresh design note — but the default is: build what
§A.5 says.

Phase 1 itself ships none of this — no token-minting code, no service-user
row, nothing under `modules/onboarding/` that authenticates as anything.
There's no caller to exercise it yet, and shipping an authentication path
nothing uses is untested-by-construction risk for no Phase 1 benefit.

### A.6 `Idempotency-Key` on `POST /api/v1/users` and `POST /api/v1/taxes`

Mechanical, mirroring the existing 15-router pattern exactly (`branch_router.py`'s
own is the clearest reference): add `idempotency_guard: IdempotencyGuardDep`
and `idempotency_key: IdempotencyKeyHeader = None` to both handlers; if the
header is absent, call the use case directly (unchanged behavior); if
present, wrap the same call through `idempotency_guard.run(tenant_id=...,
idempotency_key=..., request_fingerprint=fingerprint_request(body.model_dump()),
execute=...)`.

One thing I flagged as "debt" in the exploration report turns out to be a
non-issue here: `CreateTaxUseCase.execute(tenant_id, name, rate)` takes
primitive args instead of a DTO, but the idempotency fingerprint is
computed from the **request body schema** (`CreateTaxRequestSchema`), not
from the use case's own signature — the primitive-args shape doesn't
complicate this wiring at all. It's still worth fixing eventually (see
§9's non-negotiable — not touched here), just not blocking.

### A.7 Registry step ordering — corrected against real code, not just the spec

| Step | `requires` | Confirmed by |
|---|---|---|
| `provision_tenant` (tenant + Owner + currency, atomic — §A.4) | `[]` | root of the graph |
| `create_restaurant` | `[provision_tenant]` | — |
| `create_branch` | `[create_restaurant]` | `CreateBranchUseCase` looks up `restaurant_repo.get_by_id` |
| `configure_tax` | `[provision_tenant]` | **Checked, confirmed a real step — `CreateTaxUseCase` is genuinely create-only.** No `update_tax.py`/`delete_tax.py` anywhere in `modules/operations`; nothing to fold it into the way `configure_currency` got folded into `provision_tenant`. **Amended:** `requires` corrected to `[provision_tenant]`, not `[create_branch]` — tax is tenant-wide (`bill_router.py`'s own docstring: "`POST /api/v1/taxes` is tenant-wide, flat"), and gating it behind `create_branch` was an artificial dependency with a real cost: it serializes `configure_tax` behind the entire Floor track for no structural reason, defeating the point of the Locale/Floor/People/Catalog tracks running in parallel. `configure_tax` now unblocks as soon as `provision_tenant` verifies, same as every other track's first step. |
| ~~`configure_currency`~~ | — | **Deleted.** No backing use case existed (currency is a plain creation-time field, not something with an update path). Folded into `provision_tenant`'s `collect` schema and `verify()` — §A.4. |
| `create_table_zone` | `[create_branch]` | `CreateTableZoneUseCase` looks up `branch_repo.get_by_id` |
| `create_table` | `[create_table_zone]` | `CreateTableUseCase` looks up `table_zone_repo.get_by_id` — a real DB dependency, not just a spec assumption |
| `generate_qr_codes` | `[create_table]` | `CreateQrCodeUseCase`, one per table |
| `create_manager` / `create_waiters` / `create_kitchen_staff` | `[create_branch]` each, parallel | `CreateUserUseCase` + `AssignUserRoleUseCase`, `granter_user_id=ctx.owner_id` |
| `create_menu_category` | `[create_restaurant]`, **not** `create_branch` | `CreateMenuCategoryUseCase` looks up `restaurant_repo.get_by_id(tenant_id, request.restaurant_id)` — menu categories are restaurant-scoped. Spec §2 puts the whole Catalog track behind `create_branch`; the real dependency is one level shallower. Keeping it behind `create_branch` anyway (like tax, above) is safe, just not required by the data model. |
| `create_menu_items` | `[create_menu_category]` | `CreateMenuItemUseCase` looks up `menu_category_repo.get_by_id` |
| `add_inventory` | `[create_branch]` | scaffolded as a registry node only — full step design (bulk parsing) is Phase 3, out of scope |
| `add_recipes` | `[create_menu_items, add_inventory]` | scaffolded as a registry node only, same reason |

The last two rows are graph *scaffolding* only (StepId + `requires` edges,
enough for the reconciler to compute correct `ready` states across the
whole graph) — not full `execute`/`verify` implementations, consistent
with bulk importers being explicitly out of scope for Phase 1.

---

## B. Exact files to create/change

**New module** `services/api/src/restaurant_os_api/modules/onboarding/` —
same shape as `modules/identity`, `modules/restaurant`, `modules/operations`:

```
modules/onboarding/domain/entities/onboarding_run.py
modules/onboarding/domain/entities/onboarding_step_state.py
modules/onboarding/domain/entities/onboarding_audit_log_entry.py
modules/onboarding/domain/enums.py                  # OnboardingRunStatus, StepStatus, StepId, ActorType
modules/onboarding/domain/ports/onboarding_run_repository.py
modules/onboarding/domain/ports/onboarding_step_state_repository.py
modules/onboarding/domain/ports/onboarding_audit_log_repository.py
modules/onboarding/domain/step_contract.py            # OnboardingStep Protocol, VerifyResult, OnboardingRunContext
modules/onboarding/domain/reconciler.py                # recompute_ready_steps — pure function
modules/onboarding/application/dto/*.py                 # RunDTO, RunStateDTO, StepExecutionResultDTO
modules/onboarding/application/steps/provision_tenant_step.py
modules/onboarding/application/steps/create_restaurant_step.py
modules/onboarding/application/steps/create_branch_step.py
modules/onboarding/application/steps/create_table_zone_step.py
modules/onboarding/application/steps/create_table_step.py
modules/onboarding/application/steps/generate_qr_codes_step.py
modules/onboarding/application/steps/configure_tax_step.py
modules/onboarding/application/steps/create_manager_step.py
modules/onboarding/application/steps/create_waiters_step.py
modules/onboarding/application/steps/create_kitchen_staff_step.py
modules/onboarding/application/steps/create_menu_category_step.py
modules/onboarding/application/steps/create_menu_items_step.py
modules/onboarding/application/registry.py              # OnboardingStepRegistry
modules/onboarding/application/orchestrator.py          # OnboardingOrchestrator
modules/onboarding/infrastructure/database/models.py
modules/onboarding/infrastructure/database/repositories.py
```

No `modules/onboarding/presentation/` in Phase 1 — no HTTP surface, per
flag #3. `OnboardingOrchestrator` is exercised by tests and, later, by
whatever Phase 2/5 build on top of it.

**New identity-module files:**

```
modules/identity/domain/entities/owner_activation_token.py
modules/identity/domain/ports/owner_activation_token_repository.py
modules/identity/application/use_cases/activate_owner.py     # ActivateOwnerUseCase
modules/identity/application/use_cases/get_user.py           # GetUserUseCase — new, §A.4's verify() needs it
modules/identity/application/use_cases/get_owner_activation_token_status.py   # GetOwnerActivationTokenStatusUseCase — new, same reason
modules/identity/application/dto/owner_activation_dto.py
modules/identity/presentation/api/v1/owner_activation_router.py   # the one Phase 1 HTTP route — see below
```

**Modified existing files:**

```
modules/identity/application/services/tenant_provisioning_service.py   # provision() extension, §A.4
modules/identity/domain/events/user_events.py                          # UserCreated.created_by_user_id: str -> str | None
modules/identity/infrastructure/database/models.py                     # + OwnerActivationTokenModel
modules/identity/infrastructure/database/repositories.py               # + SQLAlchemyOwnerActivationTokenRepository
modules/identity/presentation/api/v1/users_router.py                   # Idempotency-Key, §A.6
modules/identity/presentation/dependencies.py                          # new DI wiring
modules/operations/presentation/api/v1/bill_router.py                  # Idempotency-Key on POST /taxes, §A.6
core/exceptions.py                                                     # + OwnerActivationTokenInvalidError -> 400 (single code, no Expired/Invalid split — see §A.4 amendment)
main.py                                                                 # register owner_activation_router
tests/integration/conftest.py                                          # + new tables to the truncate list
scripts/backfill_tenant_owner.py                                       # docstring retitle + same-tenant refuse-loudly guard, §A.4
platform/rate_limiting/owner_activation_limiter.py                     # new — OwnerActivationRateLimiter, §A.4
```

**One new HTTP route, and why it's not a scope violation:** `POST
/api/v1/auth/activate-owner` (public, unauthenticated — token is the
credential, exactly like a password-reset-confirm endpoint) — takes
`{token, new_password}`, calls `ActivateOwnerUseCase`. Without this, an
`INVITED` owner is permanently unreachable regardless of how correctly
`provision()` creates them — the invariant in §A.4 would be true in the
database and false in practice. This is not the "wizard frontend" (an
operator-facing onboarding UI) or the "LLM driver" — it's the minimum
public surface required for the word "activation token" to mean anything.
Flagging it explicitly since your OUT OF SCOPE list didn't mention it
either way.

**New migration:** `services/api/alembic/versions/0014_onboarding_copilot_phase1.py`
— tables per §D, plus the `CHECK` constraint and `BEFORE UPDATE` trigger on
`onboarding_runs.tenant_id` from §A.1.

**New tests:**

```
tests/unit/modules/onboarding/fakes.py
tests/unit/modules/onboarding/test_reconciler.py           # graph reconciliation, incl. parallel tracks + the recipes-needs-both join
tests/unit/modules/onboarding/test_registry.py
tests/unit/modules/onboarding/test_orchestrator.py         # idempotency replay, resume-from-executing, verify-is-sole-authority
tests/unit/modules/onboarding/steps/test_*_step.py         # one per concrete step
tests/unit/modules/identity/use_cases/test_activate_owner.py
tests/integration/modules/onboarding/test_orchestrator_integration.py   # real Postgres, proves resume + idempotency end-to-end
tests/integration/modules/identity/test_owner_provisioning.py           # real Postgres: atomic creation, RoleGrantPolicy bypass, the invariant itself
tests/integration/modules/identity/test_owner_activation_router.py   # incl. asserting unknown/expired/consumed responses are byte-identical
```

---

## C. API and security model

- **`POST /api/v1/auth/activate-owner`** — public. No `require_permission`
  gate (there's no authenticated principal yet — same category as
  `/api/v1/auth/login`). Rate-limited the same way the guest-ordering
  endpoints already are (existing rate-limiter port, reused).
- **Everything else in Phase 1 has no HTTP surface** — `OnboardingOrchestrator`
  is called in-process (by tests now, by Phase 2's wizard router or Phase
  5's LLM driver later). When either of those lands, they'll need their
  own `require_platform_admin`-gated routes wrapping the orchestrator —
  not designed here.
- **`TenantProvisioningService.provision()`'s caller** (`OnboardTenantUseCase`,
  behind `admin_tenant_router.py`) is already `require_platform_admin`-gated
  today. That's unchanged — this design only adds parameters to
  `provision()`, not new callers or a new gate.
- **The Owner grant bypasses `RoleGrantPolicy` deliberately** (§A.4) —
  this is a widening of an existing, already-accepted precedent
  (`backfill_tenant_owner.py`'s own stated justification), not a new kind
  of exception.
- **RLS posture:** every table under `modules/onboarding/` is
  RLS-exempt, platform-admin-gated. `owner_activation_tokens` **is also
  RLS-exempt — corrected during implementation**, for a different reason:
  its one read path that matters (`POST /api/v1/owner-activation`,
  activation by raw token alone) has no tenant context to supply, unlike
  `SessionRepository.get_by_refresh_token_hash`'s own precedent, whose
  caller (a refresh request) already carries `tenant_id` in its body. An
  RLS policy here would make the row unfindable by the one caller who
  needs to find it (`current_setting('app.tenant_id', true)` evaluates to
  `NULL` pre-context, and `tenant_id = NULL` is never true). Once the
  token resolves the tenant, the actual `users` row update re-enters
  through a normal `TenantContext` and is fully RLS-protected as usual —
  only the token table's own lookup is exempt. See migration 0014's
  module docstring for the full reasoning.
- **`require_platform_admin` confirmed enforced at the router, not just
  documented** — checked directly, not assumed. `admin_tenant_router.py:45`
  applies it as `APIRouter(..., dependencies=[Depends(require_platform_admin)])`
  at router-construction time, so it's structurally impossible to add a
  new route to that router without the gate — no per-route opt-in to
  forget. Any future Phase 2/5 router wrapping the orchestrator should use
  the identical `dependencies=[Depends(require_platform_admin)]` construction,
  not a per-route `Depends()`, for the same reason.

---

## D. Migration design

`0014_onboarding_copilot_phase1.py` creates: `onboarding_runs`,
`onboarding_step_states`, `onboarding_audit_log`, and
`owner_activation_tokens` — all four RLS-exempt, for two different reasons
(§A.1/§C): the first three because the tenant genuinely doesn't exist yet
for most of a run's life; the fourth because its one activation-by-raw-token
read path has no tenant context to supply, even though the tenant it
belongs to has existed since the row was inserted. `owner_activation_tokens`
otherwise keeps `sessions`' hash-only-storage pattern (`token_hash`, never
the raw token). No changes to any existing table's DDL — `UserRole
.granted_by_user_id` and `User.password_hash` are already nullable.

**Reconciling existing tenants with zero Owner grants, before the
invariant can be relied on elsewhere:**

I'm not proposing an automatic data migration for this, and I want to be
explicit about why, rather than paper over it. `backfill_tenant_owner.py`'s
own docstring states the reason plainly: *"which existing user should
become a pre-existing tenant's Tenant Owner is not mechanically derivable
from anything in today's schema... This script does not try to guess."*
A tenant can have zero, one, or several users with no way to rank them by
"most owner-like" — an automatic migration would either crash on the
ambiguous cases or silently guess wrong on the rest, and "silently wrong"
is the worse failure mode for a security-relevant grant.

What the migration **can** safely do, and should:

1. **A read-only report, run as a recurring check — not a one-time
   migration step (per your amendment).** A `SELECT tenants.id,
   tenants.legal_name FROM tenants LEFT JOIN user_roles ... LEFT JOIN
   roles ON roles.name = 'Tenant Owner' WHERE ... HAVING count(*) = 0`
   query, safe to automate and safe to run repeatedly (pure read). Running
   it once at rollout would only ever catch the pre-Phase-1 backlog; §A.4
   already established that Phase 1 doesn't stop a tenant from *degrading*
   back to zero owners later (an Owner deactivated, a grant revoked by
   mistake) — the exact same query is what would ever surface that. It
   belongs in whatever this codebase's nearest equivalent of a scheduled
   platform-ops check is, run on a cadence, not fired once and forgotten.
   Its output is the trigger for reaching for `backfill_tenant_owner.py`
   (§A.4) — the two are one operational loop, not two unrelated tasks.
2. For each tenant the check flags, an operator runs `scripts/backfill_tenant_owner.py
   --tenant-id <id> --user-id <id> --apply` — the existing tool (now with
   the same-tenant refuse-loudly guard from §A.4), used exactly as its own
   docstring describes.

There is still no proposed DB-level constraint enforcing "≥1 Owner grant
per tenant" going forward — that's a different, harder invariant than the
one §A.1's new trigger guards (single-column immutability-once-set vs.
cross-table aggregation over `user_roles`/`roles`), and I'm not proposing
that heavier one without you asking for it explicitly. The invariant in
§A.4 is a guarantee about the `provision()` code path, not a
database-enforced property. Anything that later wants to *assume* "every
tenant has an owner" (a report, a dashboard) should treat that as true for
every tenant created after this migration, and should rely on the
recurring check above — not a one-time assumption — for tenants created
before it.

---

## E. Implementation order

1. **Migration `0014`** — new tables, no behavior change yet. Nothing
   depends on this being "correct" beyond existing, so it's the lowest-risk
   place to start, and everything else needs the tables to exist.
2. **`Idempotency-Key` on `POST /api/v1/users` / `POST /api/v1/taxes`
   (§A.6)** — small, fully independent of everything else here, zero risk,
   immediately valuable on its own. Doing it early also means the
   orchestrator (step 6) is reusing a pattern that's freshly re-verified
   working, not assumed working.
3. **Atomic first-owner provisioning (§A.4)** — the highest-risk, most
   load-bearing change in this design, because it touches the tenant
   creation path every future tenant depends on. It needs to land and be
   fully tested (unit + integration, including the invariant test) *before*
   anything downstream is allowed to assume "every new tenant already has
   an Owner." `ActivateOwnerUseCase` + the activation router ship in the
   same step — an Owner nobody can activate isn't a real invariant, it's a
   database fact with no practical meaning.
4. **`OnboardingStep` contract, registry, reconciler (§A.2)** — pure new
   code, buildable and unit-testable in isolation with fakes, no
   dependency on 1–3 beyond the type definitions. Can happen in parallel
   with step 3 if you want two threads of work, but should not be
   *tested end-to-end* until step 3 is done, since `provision_tenant_step`
   is the one step whose `execute()` calls the code from step 3.
5. **Concrete step implementations** for every row in §A.7's table with a
   real backing use case (restaurant, branch, table zone, table, QR, tax,
   staff ×3, menu category, menu item) — wired into the registry. The two
   scaffolding-only rows (`add_inventory`, `add_recipes`) get their
   `requires` edges registered now but no real `execute`/`verify`.
6. **`OnboardingOrchestrator` (§A.3)** — depends on 1, 2, 4, and 5 all
   existing. This is where resumability and the dual-idempotency-guard
   branch (tenant-scoped vs. platform-scoped) get built and integration-
   tested against real Postgres, including the resume-from-`executing`
   path and a genuine crash-and-retry scenario.
7. **Co-pilot identity — design only, no code (§A.5, flag #3).** Recorded
   here as a placeholder step so Phase 2/5 have a fixed decision to build
   against, not because Phase 1 ships any of it.

Steps 1–3 are the parts I'd want fully reviewed and merged before touching
4–6 — everything past that point is new, additive, low-blast-radius code
that doesn't change how any existing tenant's data is written.

---

## F. Known limitations

Six facts about the codebase §E step 5's concrete steps had to build
around, rather than fix — each traded off deliberately, not overlooked:

1. **`CreateTaxUseCase.execute(tenant_id, name, rate)` takes primitive
   args, not a DTO.** Flagged in §A.6 as "still worth fixing eventually...
   just not blocking" and left untouched there; `ConfigureTaxStep` adapts
   to that shape as-is rather than refactoring the use case, per explicit
   instruction not to touch it.

2. **`recipe_ingredients` has no `deleted_at` column.**
   `RecipeIngredientModel` doesn't inherit `SoftDeleteMixin` — recipes are
   immutable/versioned (editing one creates a new `Recipe` row and
   repoints `menu_items.recipe_id`, per `revise_recipe.py`'s own
   docstring), so nothing in this codebase ever edits a `RecipeIngredient`
   row in place, and there's no soft-delete concept for one either. The
   one integration test that needs to simulate "an ingredient row is gone
   out from under `AddRecipesStep.verify()`" uses a hard `DELETE`, the
   only mechanism this table supports.

3. **`CreateManagerStep`/`CreateWaitersStep`/`CreateKitchenStaffStep`'s
   `verify()` proves permission *effect*, not role-grant *identity*.**
   Each checks `ResolveUserPermissionsUseCase.has(code, branch_id=...)` —
   confirmed to genuinely catch the created `UserRole` grant being
   revoked (that's what its own integration test proves) — but it cannot
   distinguish "this user holds the permission via the grant this step
   created" from "this user holds the permission via some other grant
   entirely." In the current default role catalogue
   (`tenant_provisioning_service.py`'s own seed list), `table.manage` is
   Branch-Manager-only, so `CreateManagerStep` has no live ambiguity
   today — but `order.manage` is held by both Waiter *and* Cashier, and
   `kitchen.manage` is held identically by both Kitchen Staff *and*
   Bartender. What would break it: a future step (or manual grant) also
   assigning the same user Cashier or Bartender, or a change to the
   default role catalogue that adds `table.manage`/`order.manage`/
   `kitchen.manage` to a role that doesn't hold it today — either would
   let `verify()` report `VerifySuccess` even after the *specific* grant
   this step created was revoked, so long as the overlapping role's grant
   survives. Closing this precisely would need a use case that checks
   role-grant identity directly (e.g. "does user X hold role-by-name Y"),
   which doesn't exist yet — noted inline as a `# NOTE:` in each of the
   three steps' own `verify()`.

4. **Operating-hours overlap detection is same-`day_of_week`-only.**
   `ReplaceOperatingHoursUseCase` accepts overnight windows
   (`closesAt < opensAt`, closing the following calendar day) and rejects
   overlapping open periods, but only compares entries that share the
   same `day_of_week`. It has no way to detect an overnight entry's
   spillover into the *next* day's own early-morning row (e.g. Friday
   22:00-02:00 stored on `day_of_week=5` is never compared against a
   Saturday 01:00-06:00 row on `day_of_week=6`, even though those two
   windows do overlap in real time). Cross-day overlap detection would
   need entries compared as real instants, not per-day time-of-day
   values — disclosed in the use case's own module docstring, not built.

5. **No "is this branch currently open" logic exists anywhere in the
   codebase.** `BranchStatus` (opened/temporarily_closed/
   permanently_closed) is a separate, manually-toggled field, not derived
   from `operating_hours` at all. Nothing today reads operating hours to
   answer "is this branch open right now" — reservations, the guest
   ordering flow, and reporting are all independent of it. Whenever this
   is built, it must handle overnight windows correctly (a branch open
   22:00-02:00 is still open at 01:00 the *next* calendar day) or every
   bar/pub's computed status will be wrong for several hours after
   midnight.

6. **Menu item/category presence and pricing are restaurant-level, not
   branch-level — a hotel with a restaurant and a separately-priced bar
   can't be modelled today, for two different reasons.** `MenuCategory`
   and `MenuItem` carry only `restaurant_id`/`menu_category_id`, no
   branch column at all, so which items exist has no per-branch
   mechanism whatsoever — every branch of a restaurant mechanically sees
   the identical category/item set. Pricing is subtler: a
   `MenuItemBranchPrice` override table (branch- and time-scoped) already
   exists with working entities, a repository, and admin CRUD endpoints
   — but neither `GuestGetMenuUseCase` (what a diner is quoted) nor
   `AddOrderItemUseCase` (what an order is billed) resolves it; both
   price directly off the base `MenuItem.price_amount`, so any
   `MenuItemBranchPrice` row created today is inert. Closing the pricing
   half needs a resolution helper wired into both read paths; closing the
   presence half needs branch-scoping (or an override/exclusion table)
   added to `MenuCategory`/`MenuItem`, which nothing today provides even
   partially.

7. **`GetEndOfDayReportUseCase` buckets `report_date` as one literal UTC
   calendar day, `[00:00, 24:00)` UTC — there is no per-branch timezone
   anywhere in this schema, so it cannot resolve a real local "trading
   day."** For a branch trading past local midnight, this is only
   correct by coincidence: IST is UTC+5:30, so the UTC boundary lands at
   05:30 IST, not local midnight, and a branch that closes before 05:30
   IST has every order land under the day it opened purely because of
   that offset — not because this use case understands trading days.
   **EOD reports are only correct for a branch closing before 05:30 IST,
   and only for a branch operating in IST.** Push a closing time to or
   past 05:30 IST, or run this codebase outside IST, and a real
   overnight order silently reports under the following calendar day
   instead of the night it belongs to (guarded, not fixed, by
   `TestISTOvernightBoundaryCoincidence` in `test_report_use_cases.py`,
   which pins both the coincidence and its exact failure edge so this
   breaking is caught by a red test, not a wrong report in front of an
   owner). Closing this properly needs a branch-local timezone column
   and reporting queries computed against it, not this literal UTC
   window — deliberately not built three days before a real install, to
   avoid a change touching every report query on a client-blocking
   timeline; see the surrounding commit for the full tradeoff.
