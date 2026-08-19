"""Application-layer DTOs for ``OnboardingOrchestrator`` (Phase 1 design
doc §E step 6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from restaurant_os_api.modules.onboarding.domain.enums import (
    OnboardingRunStatus,
    StepId,
    StepStatus,
)
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyResult,
)


@dataclass(frozen=True, slots=True)
class RunDTO:
    id: str
    tenant_id: str | None
    status: OnboardingRunStatus
    created_by_user_id: str
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class StepStateDTO:
    step_id: StepId
    status: StepStatus
    output: dict[str, Any] | None
    verify_evidence: str | None
    error: str | None
    attempts: int


@dataclass(frozen=True, slots=True)
class RunSnapshotDTO:
    """The full current state of a run -- what ``resume_run`` and
    ``get_snapshot`` both return. ``context`` is reconstructed from
    stored step outputs, never read off ``onboarding_runs.context``
    (see ``OnboardingOrchestrator``'s own module docstring)."""

    run: RunDTO
    steps: dict[StepId, StepStateDTO]
    context: OnboardingRunContext
    ready_step_ids: tuple[StepId, ...]


@dataclass(frozen=True, slots=True)
class StepExecutionResultDTO:
    step_id: StepId
    status: StepStatus
    verify_result: VerifyResult | None
    context: OnboardingRunContext
