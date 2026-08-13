"""Repository port for Modifier."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import Modifier


class ModifierRepository(Protocol):
    async def get_by_id(self, tenant_id: str, modifier_id: str) -> Modifier | None: ...

    async def create(self, modifier: Modifier) -> Modifier: ...

    async def update(self, modifier: Modifier) -> Modifier: ...

    async def list_for_group(self, tenant_id: str, modifier_group_id: str) -> list[Modifier]: ...
