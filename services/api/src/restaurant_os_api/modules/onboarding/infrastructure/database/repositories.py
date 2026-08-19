"""SQLAlchemy repository implementations for the onboarding module.

No ``TenantContext``/RLS involvement anywhere here (migration 0014's own
module docstring: all three tables are deliberately RLS-exempt) --
every method opens its ``UnitOfWork`` with no tenant context, the same
"no tenant known yet" mode already established for the login use case
and ``PlatformIdempotencyGuard``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from restaurant_os_api.modules.onboarding.infrastructure.database.models import (
    OnboardingAuditLogModel,
    OnboardingRunModel,
    OnboardingStepStateModel,
)


def _run_to_entity(model: OnboardingRunModel) -> OnboardingRun:
    return OnboardingRun(
        id=model.id,
        tenant_id=model.tenant_id,
        status=OnboardingRunStatus(model.status),
        created_by_user_id=model.created_by_user_id,
        context=model.context,
        started_at=model.started_at,
        completed_at=model.completed_at,
    )


def _step_state_to_entity(model: OnboardingStepStateModel) -> OnboardingStepState:
    return OnboardingStepState(
        id=model.id,
        run_id=model.run_id,
        step_id=StepId(model.step_id),
        status=StepStatus(model.status),
        input=model.input,
        output=model.output,
        idempotency_key=model.idempotency_key,
        verify_evidence=model.verify_evidence,
        error=model.error,
        attempts=model.attempts,
        updated_at=model.updated_at,
    )


def _audit_entry_to_entity(model: OnboardingAuditLogModel) -> OnboardingAuditLogEntry:
    return OnboardingAuditLogEntry(
        id=model.id,
        run_id=model.run_id,
        step_id=StepId(model.step_id) if model.step_id is not None else None,
        actor_type=ActorType(model.actor_type),
        actor_id=model.actor_id,
        action=model.action,
        request=model.request,
        response=model.response,
        at=model.at,
    )


class SQLAlchemyOnboardingRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, run: OnboardingRun) -> OnboardingRun:
        model = OnboardingRunModel(
            id=run.id,
            tenant_id=run.tenant_id,
            status=run.status.value,
            created_by_user_id=run.created_by_user_id,
            context=run.context,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _run_to_entity(model)

    async def get_by_id(self, run_id: str) -> OnboardingRun | None:
        model = await self._session.get(OnboardingRunModel, run_id)
        return _run_to_entity(model) if model is not None else None

    async def update(self, run: OnboardingRun) -> OnboardingRun:
        model = await self._session.get(OnboardingRunModel, run.id)
        assert model is not None, f"onboarding_runs row {run.id} vanished mid-update"
        model.tenant_id = run.tenant_id
        model.status = run.status.value
        model.context = run.context
        model.completed_at = run.completed_at
        await self._session.flush()
        return _run_to_entity(model)


class SQLAlchemyOnboardingStepStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, states: list[OnboardingStepState]) -> None:
        self._session.add_all(
            [
                OnboardingStepStateModel(
                    id=state.id,
                    run_id=state.run_id,
                    step_id=state.step_id.value,
                    status=state.status.value,
                    input=state.input,
                    output=state.output,
                    idempotency_key=state.idempotency_key,
                    verify_evidence=state.verify_evidence,
                    error=state.error,
                    attempts=state.attempts,
                    updated_at=state.updated_at,
                )
                for state in states
            ]
        )
        await self._session.flush()

    async def get(self, run_id: str, step_id: StepId) -> OnboardingStepState | None:
        stmt = select(OnboardingStepStateModel).where(
            OnboardingStepStateModel.run_id == run_id,
            OnboardingStepStateModel.step_id == step_id.value,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _step_state_to_entity(model) if model is not None else None

    async def list_for_run(self, run_id: str) -> list[OnboardingStepState]:
        stmt = select(OnboardingStepStateModel).where(
            OnboardingStepStateModel.run_id == run_id
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_step_state_to_entity(m) for m in models]

    async def update(self, state: OnboardingStepState) -> OnboardingStepState:
        model = await self._session.get(OnboardingStepStateModel, state.id)
        assert model is not None, f"onboarding_step_states row {state.id} vanished mid-update"
        model.status = state.status.value
        model.input = state.input
        model.output = state.output
        model.idempotency_key = state.idempotency_key
        model.verify_evidence = state.verify_evidence
        model.error = state.error
        model.attempts = state.attempts
        await self._session.flush()
        return _step_state_to_entity(model)


class SQLAlchemyOnboardingAuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entry: OnboardingAuditLogEntry) -> OnboardingAuditLogEntry:
        model = OnboardingAuditLogModel(
            id=entry.id,
            run_id=entry.run_id,
            step_id=entry.step_id.value if entry.step_id is not None else None,
            actor_type=entry.actor_type.value,
            actor_id=entry.actor_id,
            action=entry.action,
            request=entry.request,
            response=entry.response,
            at=entry.at,
        )
        self._session.add(model)
        await self._session.flush()
        return _audit_entry_to_entity(model)

    async def list_for_run(self, run_id: str) -> list[OnboardingAuditLogEntry]:
        stmt = select(OnboardingAuditLogModel).where(OnboardingAuditLogModel.run_id == run_id)
        models = (await self._session.execute(stmt)).scalars().all()
        return [_audit_entry_to_entity(m) for m in models]
