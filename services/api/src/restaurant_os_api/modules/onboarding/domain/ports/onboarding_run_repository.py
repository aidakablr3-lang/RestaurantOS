from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.onboarding.domain.entities import OnboardingRun


class OnboardingRunRepository(Protocol):
    async def create(self, run: OnboardingRun) -> OnboardingRun: ...

    async def get_by_id(self, run_id: str) -> OnboardingRun | None: ...

    async def update(self, run: OnboardingRun) -> OnboardingRun: ...
