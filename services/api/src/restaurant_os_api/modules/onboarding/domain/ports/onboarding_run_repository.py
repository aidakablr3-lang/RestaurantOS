from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.onboarding.domain.entities import OnboardingRun


class OnboardingRunRepository(Protocol):
    async def create(self, run: OnboardingRun) -> OnboardingRun: ...

    async def get_by_id(self, run_id: str) -> OnboardingRun | None: ...

    async def update(self, run: OnboardingRun) -> OnboardingRun: ...

    async def delete(self, run_id: str) -> None:
        """Hard-deletes the run row. ``onboarding_step_states``/
        ``onboarding_audit_log`` rows for it cascade via their own FK
        (migration 0014's own ``ondelete="CASCADE"``) -- one call here
        is enough to leave zero rows across all three tables. Used only
        for the ``provision_tenant``-fails compensating cleanup (see
        ``OnboardingOrchestrator``'s own module docstring); nothing else
        in Phase 1 deletes a run."""
        ...
