from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.onboarding.domain.entities import OnboardingAuditLogEntry


class OnboardingAuditLogRepository(Protocol):
    async def create(self, entry: OnboardingAuditLogEntry) -> OnboardingAuditLogEntry: ...

    async def list_for_run(self, run_id: str) -> list[OnboardingAuditLogEntry]: ...
