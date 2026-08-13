"""Repository port for Tab."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import Tab


class TabRepository(Protocol):
    async def get_by_id(self, tenant_id: str, tab_id: str) -> Tab | None: ...

    async def create(self, tab: Tab) -> Tab: ...

    async def update(self, tab: Tab) -> Tab: ...
