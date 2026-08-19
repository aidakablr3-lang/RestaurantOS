"""OnboardingAuditLogEntry entity -- one row per ``execute()``/``verify()``
call the orchestrator makes (design doc §A.3).

``actor_type``/``actor_id`` are always ``'copilot'``/``ctx.owner_id``
for every row this module writes -- the deferred per-run service-user
identity decision (§A.5) resolved to "the orchestrator already has a
real, permission-holding actor for free, sitting in ``ctx.owner_id``,"
so there is no separate copilot identity to construct in Phase 1.
``actor_id`` is nullable (and the FK is ``ON DELETE SET NULL``) purely
for the one case where it is genuinely unknown: the ``execute`` call
for ``provision_tenant`` itself, before the Owner it is about to create
exists -- see the orchestrator's own module docstring for exactly when
it resolves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from restaurant_os_api.modules.onboarding.domain.enums import ActorType, StepId


@dataclass(slots=True)
class OnboardingAuditLogEntry:
    id: str
    run_id: str
    step_id: StepId | None
    actor_type: ActorType
    actor_id: str | None
    action: str
    request: dict[str, Any]
    response: dict[str, Any]
    at: datetime
