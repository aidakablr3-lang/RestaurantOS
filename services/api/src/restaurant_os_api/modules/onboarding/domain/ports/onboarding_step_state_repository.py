from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.onboarding.domain.entities import OnboardingStepState
from restaurant_os_api.modules.onboarding.domain.enums import StepId


class OnboardingStepStateRepository(Protocol):
    async def create_many(self, states: list[OnboardingStepState]) -> None:
        """Bulk-inserts the initial 14-row seed for a new run in one
        call, mirroring how the run is seeded all at once (§A.1)."""
        ...

    async def get(self, run_id: str, step_id: StepId) -> OnboardingStepState | None: ...

    async def list_for_run(self, run_id: str) -> list[OnboardingStepState]: ...

    async def update(self, state: OnboardingStepState) -> OnboardingStepState: ...
