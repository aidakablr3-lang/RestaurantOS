"""Repository port for OperatingHours."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import OperatingHours


class OperatingHoursRepository(Protocol):
    async def list_for_branch(self, tenant_id: str, branch_id: str) -> list[OperatingHours]: ...

    async def replace_for_branch(
        self, tenant_id: str, branch_id: str, rows: list[OperatingHours]
    ) -> None:
        """Full-week replace, matching ``PUT /branches/{id}/operating-hours``
        (Restaurant Platform Architecture SS7) -- the Blueprint's Branch
        Settings screen edits the whole week at once, not per-day."""
        ...
