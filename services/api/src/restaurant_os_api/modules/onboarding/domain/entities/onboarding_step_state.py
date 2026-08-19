"""OnboardingStepState entity -- one row per ``(run_id, step_id)`` pair,
seeded for all 14 steps at run creation (migration 0014 / design doc
§A.1).

``input``/``output`` are JSONB, not the step's real ``TInput``/
``TOutput`` -- ``input`` is the validated ``collect_schema`` instance
dumped to JSON (``model_dump(mode="json")``), and ``output`` is not the
step's raw return value (heterogeneous across all 14 steps -- DTOs,
dataclasses, tuples of either, a bare domain entity) but the small,
uniformly-shaped ``OnboardingRunContext`` delta this step contributes,
per ``OnboardingOrchestrator``'s own per-step mapping. That delta is
exactly what resume needs to reconstruct context and is what actually
gets cached/replayed by the idempotency guard on retry -- see the
orchestrator's own module docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from restaurant_os_api.modules.onboarding.domain.enums import StepId, StepStatus


@dataclass(slots=True)
class OnboardingStepState:
    id: str
    run_id: str
    step_id: StepId
    status: StepStatus
    input: dict[str, Any] | None
    output: dict[str, Any] | None
    idempotency_key: str | None
    verify_evidence: str | None
    error: str | None
    attempts: int
    updated_at: datetime
