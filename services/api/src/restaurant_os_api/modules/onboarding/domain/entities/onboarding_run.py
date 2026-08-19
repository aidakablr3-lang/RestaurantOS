"""OnboardingRun entity -- Phase 1 design doc §A.1 / migration 0014.

One row per Setup Copilot run. ``tenant_id`` starts ``None`` (the
tenant genuinely doesn't exist until ``provision_tenant`` verifies) and
is set exactly once thereafter, immutable -- enforced in the database
by the migration's own CHECK constraint and ``BEFORE UPDATE`` trigger,
not re-checked here (this codebase's domain entities don't re-validate
invariants their own migration already guarantees at the storage
layer; see ``UserRole``'s own docstring for the same convention).

``context`` is a JSONB snapshot column the migration provides, kept
here as a non-authoritative convenience cache (e.g. for a future UI to
render current state without joining ``onboarding_step_states``) --
the orchestrator's actual resume path reconstructs
``OnboardingRunContext`` from each verified step's own stored
``output``, never from this column. See ``OnboardingOrchestrator``'s
own module docstring for why.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from restaurant_os_api.modules.onboarding.domain.enums import OnboardingRunStatus


@dataclass(slots=True)
class OnboardingRun:
    id: str
    tenant_id: str | None
    status: OnboardingRunStatus
    created_by_user_id: str
    context: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None
