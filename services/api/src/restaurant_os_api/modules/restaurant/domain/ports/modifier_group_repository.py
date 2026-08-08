"""Repository port for ModifierGroup."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import ModifierGroup


class ModifierGroupRepository(Protocol):
    async def get_by_id(self, tenant_id: str, modifier_group_id: str) -> ModifierGroup | None: ...

    async def create(self, modifier_group: ModifierGroup) -> ModifierGroup: ...

    async def update(self, modifier_group: ModifierGroup) -> ModifierGroup: ...

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[ModifierGroup], int]: ...
