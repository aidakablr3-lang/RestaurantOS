"""OnboardingOrchestrator -- Phase 1 design doc §A.3 / §E step 6.

Drives one run's lifecycle over the persistence from §E steps 1-3
(migration 0014's three tables) and the registry/reconciler from §E
steps 4-5. **No HTTP layer, no wizard, no LLM** -- exercised by tests
now, by whatever Phase 2/5 build on top of it later (§C).

**Why every bookkeeping write opens its own short ``UnitOfWork``.**
This codebase's own convention (every existing use case, and
``PlatformIdempotencyGuard``'s own ``_try_claim``/``_resolve_existing``/
``_record_response``): no cross-cutting transaction spanning multiple
use-case calls. A step's real side effect happens inside whatever
``UnitOfWork`` the wrapped use case opens for itself (invisible to the
orchestrator); the orchestrator's own reads/writes to the three
onboarding tables are separate, short transactions with no
``TenantContext`` (migration 0014: all three are RLS-exempt, the same
"no tenant known yet" mode already established for
``PlatformIdempotencyGuard`` and the login use case).

**Why ``onboarding_step_states.output`` holds a ctx delta, not the
step's raw return value.** Each concrete step's ``TOutput`` is
heterogeneous across all 14 steps -- DTOs, small dataclasses, tuples of
either, or a bare domain entity -- with no common JSON-safe shape.
What every later step and a resumed run actually need is much
narrower: the handful of ``OnboardingRunContext`` fields this one step
contributes (e.g. ``{"branch_id": "01..."}``). ``_ctx_delta`` is the
one place that heterogeneity gets resolved, per ``StepId`` -- a small,
explicit mapping kept in this module rather than added to the
``OnboardingStep`` Protocol itself (§E step 5's already-committed,
already-tested 14 step classes stay untouched; the orchestrator is the
one place downstream of them that needs this knowledge, so it owns it).

**Idempotency.** ``execute()``'s own real side effect happens inside
the existing ``IdempotencyGuard``/``PlatformIdempotencyGuard`` claim
protocol (§A.6) -- the *same* infrastructure already proven for
``POST /users``/``POST /taxes``, reused here rather than reinvented.
The orchestrator's own call to a step's ``execute()`` is the guarded
operation: ``idempotency_key = hash(run_id, step_id, canonical(payload))``
(``canonical()`` is this codebase's own ``fingerprint_request`` --
already named exactly that in its own docstring), and the guard's
claim-row-before-execute mechanism guarantees the wrapped use case
runs at most once per key, regardless of how many times the
orchestrator itself gets asked to attempt that step. ``provision_tenant``
is the one step with no ``ctx.tenant_id`` yet, so it alone goes
through ``PlatformIdempotencyGuard``; every other step requires
``provision_tenant`` transitively, so ``ctx.tenant_id`` is always set
by the time any of them can be ``ready``, and they use the tenant-scoped
``IdempotencyGuard``.

**Resume.** Reloading a run reconstructs ``OnboardingRunContext`` by
folding every ``verified`` step's stored ``output`` delta, in
topological order -- never from ``onboarding_runs.context`` (that
column is a non-authoritative snapshot; see the ``OnboardingRun``
entity's own docstring). If a step is found in ``executing`` (the
process crashed between "claimed this attempt" and "recorded the
result"), resume re-drives *that exact step* to completion using its
own already-persisted ``input`` -- re-validated through
``collect_schema``, recomputing the identical idempotency key -- rather
than asking the caller to resupply input it may no longer have. Because
the key is identical, the guard either replays the cached result (the
use case's own write already committed before the crash) or completes
a fresh claim (it hadn't) -- either way the underlying use case runs
at most once.

**Failure.** ``VerifyFailure`` (or ``execute()`` raising) marks the
step ``failed`` with the reason/exception persisted, and
``reblock_transitive_dependents`` (the reconciler's own counterpart to
``recompute_ready_steps``) walks the graph forward demoting any
``ready`` dependent back to ``blocked``. The run itself is never marked
``abandoned`` and never deleted by a step failure -- not even
``provision_tenant``'s: nothing else can have executed before the
graph's root fails, so there is nothing to clean up, and the run
persisting with ``tenant_id`` still null and the failure reason on
record is exactly what diagnosing the failure needs. The run stays
``in_progress`` and resumable, exactly the "not wedged" requirement;
only reaching ``verified`` on all 14 steps completes it.

**Retry.** ``execute_step`` accepts a step in either ``ready`` or
``failed`` status -- a failed step is not a dead end. A retry attempt
is driven through the exact same collect -> autofill -> execute ->
verify path as a first attempt, with its own idempotency key (payload-
dependent, so a genuinely different retry payload -- a corrected name,
a fixed price -- gets a fresh attempt rather than replaying the failed
one's cached result; an unchanged payload after an ``execute()``-raised
failure also gets a fresh attempt, since the idempotency guard releases
its claim on an exception rather than caching it -- see
``IdempotencyGuard``'s own docstring). On success, ``_succeed_step``'s
own ``recompute_ready_steps`` call unblocks any dependent left
``blocked`` by the earlier failure exactly as it would on a first
success -- no separate "un-reblock" path is needed.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.onboarding.application.dto import (
    RunDTO,
    RunSnapshotDTO,
    StepExecutionResultDTO,
    StepStateDTO,
)
from restaurant_os_api.modules.onboarding.application.registry import OnboardingStepRegistry
from restaurant_os_api.modules.onboarding.application.steps.add_recipes_step import (
    AddRecipesStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.provision_tenant_step import (
    ProvisionTenantStepInput,
)
from restaurant_os_api.modules.onboarding.domain.entities import (
    OnboardingAuditLogEntry,
    OnboardingRun,
    OnboardingStepState,
)
from restaurant_os_api.modules.onboarding.domain.enums import (
    ActorType,
    OnboardingRunStatus,
    StepId,
    StepStatus,
)
from restaurant_os_api.modules.onboarding.domain.ports import (
    OnboardingAuditLogRepository,
    OnboardingRunRepository,
    OnboardingStepStateRepository,
)
from restaurant_os_api.modules.onboarding.domain.reconciler import (
    reblock_transitive_dependents,
    recompute_ready_steps,
)
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.idempotency import (
    IdempotencyGuard,
    PlatformIdempotencyGuard,
    fingerprint_request,
)


class StepNotReadyError(Exception):
    def __init__(self, step_id: StepId, actual_status: StepStatus) -> None:
        self.step_id = step_id
        self.actual_status = actual_status
        super().__init__(f"step {step_id} is '{actual_status}', not 'ready' or 'failed'")


class OnboardingOrchestrator:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        registry: OnboardingStepRegistry,
        run_repository_factory: Callable[[AsyncSession], OnboardingRunRepository],
        step_state_repository_factory: Callable[[AsyncSession], OnboardingStepStateRepository],
        audit_log_repository_factory: Callable[[AsyncSession], OnboardingAuditLogRepository],
        idempotency_guard: IdempotencyGuard,
        platform_idempotency_guard: PlatformIdempotencyGuard,
    ) -> None:
        self._session_factory = session_factory
        self._registry = registry
        self._run_repository_factory = run_repository_factory
        self._step_state_repository_factory = step_state_repository_factory
        self._audit_log_repository_factory = audit_log_repository_factory
        self._idempotency_guard = idempotency_guard
        self._platform_idempotency_guard = platform_idempotency_guard
        self._requires_graph = registry.requires_graph()
        self._direct_dependents_graph = {
            step_id: registry.direct_dependents(step_id) for step_id in registry.all_step_ids()
        }

    # --- run lifecycle ------------------------------------------------

    async def start_run(self, created_by_user_id: str) -> RunDTO:
        now = datetime.now(UTC)
        run = OnboardingRun(
            id=generate_ulid(),
            tenant_id=None,
            status=OnboardingRunStatus.IN_PROGRESS,
            created_by_user_id=created_by_user_id,
            context={},
            started_at=now,
        )
        await self._create_run(run)

        initial = {step_id: StepStatus.BLOCKED for step_id in self._registry.all_step_ids()}
        seeded = recompute_ready_steps(initial, self._requires_graph)
        await self._create_states(
            [
                OnboardingStepState(
                    id=generate_ulid(),
                    run_id=run.id,
                    step_id=step_id,
                    status=status,
                    input=None,
                    output=None,
                    idempotency_key=None,
                    verify_evidence=None,
                    error=None,
                    attempts=0,
                    updated_at=now,
                )
                for step_id, status in seeded.items()
            ]
        )
        return _run_dto(run)

    async def get_snapshot(self, run_id: str) -> RunSnapshotDTO:
        run, states = await self._load(run_id)
        ctx = self._reconstruct_context(states)
        return self._snapshot(run, states, ctx)

    async def resume_run(self, run_id: str) -> RunSnapshotDTO:
        """Reconstructs context from persistence and, if a step was
        left ``executing`` by a crash, re-drives that exact step to
        completion (execute-replay-or-complete, then verify) before
        returning the resulting snapshot. A step left ``ready`` (no
        attempt was ever recorded) is *not* auto-driven -- the caller
        still supplies its input via ``execute_step``, same as a fresh
        run; only an attempt already in flight gets resumed
        automatically, since only that case has stored ``input`` to
        resume *with*."""
        run, states = await self._load(run_id)
        executing = [s for s in states.values() if s.status == StepStatus.EXECUTING]
        for state in executing:
            step = self._registry[state.step_id]
            assert state.input is not None, (
                f"step {state.step_id} is 'executing' with no stored input -- "
                "should be unreachable (input is written in the same call that "
                "sets status='executing')"
            )
            validated_input = step.collect_schema.model_validate(state.input)
            await self._run_step(run, state, validated_input)
            run, states = await self._load(run_id)
        ctx = self._reconstruct_context(states)
        return self._snapshot(run, states, ctx)

    async def execute_step(
        self, run_id: str, step_id: StepId, raw_input: dict[str, Any]
    ) -> StepExecutionResultDTO:
        """A step in ``ready`` gets its first attempt; a step in
        ``failed`` gets a retry -- both go through the identical
        collect -> autofill -> execute -> verify path below. Any other
        status (``blocked``, ``executing``, ``verified``, ...) is
        rejected -- see this module's own docstring's "Retry" section."""
        run, states = await self._load(run_id)
        state = states.get(step_id)
        if state is None or state.status not in (StepStatus.READY, StepStatus.FAILED):
            actual = state.status if state is not None else StepStatus.BLOCKED
            raise StepNotReadyError(step_id, actual)

        ctx = self._reconstruct_context(states)
        step = self._registry[step_id]
        collected = {**step.autofill(ctx), **raw_input}
        validated_input = step.collect_schema.model_validate(collected)

        result_state = await self._run_step(run, state, validated_input)
        _run2, states2 = await self._load(run_id)
        ctx2 = self._reconstruct_context(states2)
        return StepExecutionResultDTO(
            step_id=step_id,
            status=result_state.status,
            verify_result=_parse_verify_result(result_state),
            context=ctx2,
        )

    # --- one step's execute -> verify -> reconcile tail ----------------

    async def _run_step(
        self, run: OnboardingRun, state: OnboardingStepState, validated_input: Any
    ) -> OnboardingStepState:
        """Shared by ``execute_step`` (fresh attempt) and ``resume_run``
        (re-driving a crashed ``executing`` attempt) -- both already
        have a real ``validated_input`` by the time they call this."""
        step = self._registry[state.step_id]
        _run, current_states = await self._load(run.id)
        ctx = self._reconstruct_context(current_states)

        idempotency_key = _idempotency_key(run.id, state.step_id, validated_input)
        now = datetime.now(UTC)
        state = OnboardingStepState(
            id=state.id,
            run_id=state.run_id,
            step_id=state.step_id,
            status=StepStatus.EXECUTING,
            input=validated_input.model_dump(mode="json"),
            output=state.output,
            idempotency_key=idempotency_key,
            verify_evidence=state.verify_evidence,
            error=state.error,
            attempts=state.attempts + 1,
            updated_at=now,
        )
        await self._update_state(state)

        try:
            delta = await self._guarded_execute(
                run, state.step_id, validated_input, ctx, idempotency_key
            )
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: any execute() failure is a step failure
            return await self._fail_step(run, state, error=f"execute() raised: {exc}")

        ctx_after_execute = ctx.model_copy(update=delta)
        await self._audit(
            run_id=run.id,
            step_id=state.step_id,
            actor_id=ctx_after_execute.owner_id,
            action="execute",
            request=validated_input.model_dump(mode="json"),
            response=delta,
        )
        state = OnboardingStepState(
            id=state.id,
            run_id=state.run_id,
            step_id=state.step_id,
            status=StepStatus.EXECUTING,
            input=state.input,
            output=delta,
            idempotency_key=state.idempotency_key,
            verify_evidence=state.verify_evidence,
            error=None,
            attempts=state.attempts,
            updated_at=datetime.now(UTC),
        )
        await self._update_state(state)

        verify_result: VerifyResult = await step.verify(ctx_after_execute)
        await self._audit(
            run_id=run.id,
            step_id=state.step_id,
            actor_id=ctx_after_execute.owner_id,
            action="verify",
            request={},
            response=verify_result.model_dump(mode="json"),
        )

        if isinstance(verify_result, VerifySuccess):
            return await self._succeed_step(run, state, verify_result)
        return await self._fail_step(run, state, error=verify_result.reason)

    async def _guarded_execute(
        self,
        run: OnboardingRun,
        step_id: StepId,
        validated_input: Any,
        ctx: OnboardingRunContext,
        idempotency_key: str,
    ) -> dict[str, Any]:
        step = self._registry[step_id]
        fingerprint = fingerprint_request(validated_input.model_dump(mode="json"))

        async def _do_execute() -> tuple[int, dict[str, Any]]:
            output = await step.execute(validated_input, ctx)
            return 200, _ctx_delta(step_id, validated_input, output)

        if step_id == StepId.PROVISION_TENANT:
            _, delta = await self._platform_idempotency_guard.run(
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                execute=_do_execute,
            )
        else:
            assert ctx.tenant_id is not None, (
                f"step {step_id} became ready with no ctx.tenant_id -- every step but "
                "provision_tenant requires it transitively, so this should be unreachable"
            )
            _, delta = await self._idempotency_guard.run(
                tenant_id=ctx.tenant_id,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                execute=_do_execute,
            )
        return delta

    # --- terminal transitions ------------------------------------------

    async def _succeed_step(
        self, run: OnboardingRun, state: OnboardingStepState, verify_result: VerifySuccess
    ) -> OnboardingStepState:
        state = OnboardingStepState(
            id=state.id,
            run_id=state.run_id,
            step_id=state.step_id,
            status=StepStatus.VERIFIED,
            input=state.input,
            output=state.output,
            idempotency_key=state.idempotency_key,
            verify_evidence=verify_result.evidence,
            error=None,
            attempts=state.attempts,
            updated_at=datetime.now(UTC),
        )
        await self._update_state(state)

        states = await self._states_by_id(run.id)
        statuses = {sid: s.status for sid, s in states.items()}
        reconciled = recompute_ready_steps(statuses, self._requires_graph)
        for step_id, new_status in reconciled.items():
            if new_status != statuses[step_id]:
                await self._update_state(_with_status(states[step_id], new_status))

        if state.step_id == StepId.PROVISION_TENANT:
            assert state.output is not None
            tenant_id = state.output.get("tenant_id")
            assert isinstance(tenant_id, str)
            run = OnboardingRun(
                id=run.id,
                tenant_id=tenant_id,
                status=run.status,
                created_by_user_id=run.created_by_user_id,
                context=run.context,
                started_at=run.started_at,
                completed_at=run.completed_at,
            )
            await self._update_run(run)

        if all(status == StepStatus.VERIFIED for status in reconciled.values()):
            run = OnboardingRun(
                id=run.id,
                tenant_id=run.tenant_id,
                status=OnboardingRunStatus.COMPLETED,
                created_by_user_id=run.created_by_user_id,
                context=run.context,
                started_at=run.started_at,
                completed_at=datetime.now(UTC),
            )
            await self._update_run(run)

        return state

    async def _fail_step(
        self, run: OnboardingRun, state: OnboardingStepState, *, error: str
    ) -> OnboardingStepState:
        state = OnboardingStepState(
            id=state.id,
            run_id=state.run_id,
            step_id=state.step_id,
            status=StepStatus.FAILED,
            input=state.input,
            output=state.output,
            idempotency_key=state.idempotency_key,
            verify_evidence=None,
            error=error,
            attempts=state.attempts,
            updated_at=datetime.now(UTC),
        )
        await self._update_state(state)

        states = await self._states_by_id(run.id)
        statuses = {sid: s.status for sid, s in states.items()}
        reblocked = reblock_transitive_dependents(
            statuses, state.step_id, self._direct_dependents_graph
        )
        for step_id, new_status in reblocked.items():
            if new_status != statuses[step_id]:
                await self._update_state(_with_status(states[step_id], new_status))

        return state

    # --- context reconstruction -----------------------------------------

    def _reconstruct_context(
        self, states: dict[StepId, OnboardingStepState]
    ) -> OnboardingRunContext:
        ctx = OnboardingRunContext()
        for step_id in self._registry.topological_order():
            state = states.get(step_id)
            if state is None or state.status != StepStatus.VERIFIED or state.output is None:
                continue
            ctx = ctx.model_copy(update=_deserialize_delta(state.output))
        return ctx

    def _snapshot(
        self,
        run: OnboardingRun,
        states: dict[StepId, OnboardingStepState],
        ctx: OnboardingRunContext,
    ) -> RunSnapshotDTO:
        ready = tuple(
            step_id
            for step_id in self._registry.topological_order()
            if states.get(step_id) is not None and states[step_id].status == StepStatus.READY
        )
        return RunSnapshotDTO(
            run=_run_dto(run),
            steps={step_id: _step_state_dto(state) for step_id, state in states.items()},
            context=ctx,
            ready_step_ids=ready,
        )

    # --- persistence: one short UnitOfWork per call, no TenantContext ---

    async def _create_run(self, run: OnboardingRun) -> None:
        async with UnitOfWork(self._session_factory) as uow:
            repo = self._run_repository_factory(uow.session)
            await repo.create(run)

    async def _update_run(self, run: OnboardingRun) -> None:
        async with UnitOfWork(self._session_factory) as uow:
            repo = self._run_repository_factory(uow.session)
            await repo.update(run)

    async def _create_states(self, states: list[OnboardingStepState]) -> None:
        async with UnitOfWork(self._session_factory) as uow:
            repo = self._step_state_repository_factory(uow.session)
            await repo.create_many(states)

    async def _update_state(self, state: OnboardingStepState) -> None:
        async with UnitOfWork(self._session_factory) as uow:
            repo = self._step_state_repository_factory(uow.session)
            await repo.update(state)

    async def _states_by_id(self, run_id: str) -> dict[StepId, OnboardingStepState]:
        async with UnitOfWork(self._session_factory) as uow:
            repo = self._step_state_repository_factory(uow.session)
            states = await repo.list_for_run(run_id)
        return {s.step_id: s for s in states}

    async def _load(self, run_id: str) -> tuple[OnboardingRun, dict[StepId, OnboardingStepState]]:
        async with UnitOfWork(self._session_factory) as uow:
            run_repo = self._run_repository_factory(uow.session)
            state_repo = self._step_state_repository_factory(uow.session)
            run = await run_repo.get_by_id(run_id)
            assert run is not None, f"onboarding run {run_id} not found"
            states = await state_repo.list_for_run(run_id)
        return run, {s.step_id: s for s in states}

    async def _audit(
        self,
        *,
        run_id: str,
        step_id: StepId,
        actor_id: str | None,
        action: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        async with UnitOfWork(self._session_factory) as uow:
            repo = self._audit_log_repository_factory(uow.session)
            await repo.create(
                OnboardingAuditLogEntry(
                    id=generate_ulid(),
                    run_id=run_id,
                    step_id=step_id,
                    actor_type=ActorType.COPILOT,
                    actor_id=actor_id,
                    action=action,
                    request=request,
                    response=response,
                    at=datetime.now(UTC),
                )
            )


# --- module-level helpers ---------------------------------------------


def _idempotency_key(run_id: str, step_id: StepId, validated_input: Any) -> str:
    payload_fingerprint = fingerprint_request(validated_input.model_dump(mode="json"))
    canonical = f"{run_id}:{step_id.value}:{payload_fingerprint}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _with_status(state: OnboardingStepState, status: StepStatus) -> OnboardingStepState:
    return OnboardingStepState(
        id=state.id,
        run_id=state.run_id,
        step_id=state.step_id,
        status=status,
        input=state.input,
        output=state.output,
        idempotency_key=state.idempotency_key,
        verify_evidence=state.verify_evidence,
        error=state.error,
        attempts=state.attempts,
        updated_at=datetime.now(UTC),
    )


def _run_dto(run: OnboardingRun) -> RunDTO:
    return RunDTO(
        id=run.id,
        tenant_id=run.tenant_id,
        status=run.status,
        created_by_user_id=run.created_by_user_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _step_state_dto(state: OnboardingStepState) -> StepStateDTO:
    return StepStateDTO(
        step_id=state.step_id,
        status=state.status,
        output=state.output,
        verify_evidence=state.verify_evidence,
        error=state.error,
        attempts=state.attempts,
    )


def _parse_verify_result(state: OnboardingStepState) -> VerifyResult | None:
    if state.status == StepStatus.VERIFIED:
        assert state.verify_evidence is not None
        return VerifySuccess(evidence=state.verify_evidence)
    if state.status == StepStatus.FAILED:
        assert state.error is not None
        return VerifyFailure(reason=state.error)
    return None


def _deserialize_delta(output: dict[str, Any]) -> dict[str, Any]:
    """``output`` round-trips through JSONB, so tuple-typed
    ``OnboardingRunContext`` fields (``table_ids``, ``waiter_ids``,
    ``kitchen_staff_ids``, ``menu_item_ids``) come back as JSON lists --
    cast them back to tuples so ``ctx.model_copy(update=...)`` produces
    the same shape ``OnboardingRunContext``'s own field types declare."""
    _tuple_fields = {"table_ids", "waiter_ids", "kitchen_staff_ids", "menu_item_ids"}
    return {
        key: tuple(value) if key in _tuple_fields and isinstance(value, list) else value
        for key, value in output.items()
    }


def _ctx_delta(step_id: StepId, validated_input: Any, output: Any) -> dict[str, Any]:
    """The one place §E step 5's 14 heterogeneous ``TOutput`` shapes get
    reduced to the ``OnboardingRunContext`` fields each step actually
    contributes -- see this module's own docstring for why this lives
    here rather than on each step class. Grounded directly against each
    step file's own ``execute()``/``verify()`` for the exact field to
    read, not guessed from the field's name alone (e.g.
    ``add_recipes``'s delta is ``input.menu_item_id``, not
    ``output.id`` -- ``ctx.recipe_menu_item_id`` means "the menu item
    this step attached a recipe to," which ``AddRecipesStep.verify()``
    itself keys its read-back by)."""
    match step_id:
        case StepId.PROVISION_TENANT:
            assert isinstance(validated_input, ProvisionTenantStepInput)
            return {
                "tenant_id": output.tenant_id,
                "owner_id": output.owner_id,
                "expected_currency_code": validated_input.default_currency_code,
            }
        case StepId.CREATE_RESTAURANT:
            return {"restaurant_id": output.id}
        case StepId.CREATE_BRANCH:
            return {"branch_id": output.id}
        case StepId.CREATE_TABLE_ZONE:
            return {"table_zone_id": output.id}
        case StepId.CREATE_TABLE:
            return {"table_ids": tuple(item.id for item in output)}
        case StepId.GENERATE_QR_CODES:
            return {}
        case StepId.CONFIGURE_TAX:
            return {"tax_id": output.id}
        case StepId.CREATE_MANAGER:
            return {"manager_id": output.user_id}
        case StepId.CREATE_WAITERS:
            return {"waiter_ids": tuple(item.user_id for item in output)}
        case StepId.CREATE_KITCHEN_STAFF:
            return {"kitchen_staff_ids": tuple(item.user_id for item in output)}
        case StepId.CREATE_MENU_CATEGORY:
            return {"menu_category_id": output.id}
        case StepId.CREATE_MENU_ITEMS:
            return {"menu_item_ids": tuple(item.id for item in output)}
        case StepId.ADD_INVENTORY:
            return {"inventory_item_id": output.id}
        case StepId.ADD_RECIPES:
            assert isinstance(validated_input, AddRecipesStepInput)
            return {"recipe_menu_item_id": validated_input.menu_item_id}
    raise AssertionError(f"unhandled StepId in _ctx_delta: {step_id}")
