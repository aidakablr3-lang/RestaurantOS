"""Repository port for Tax."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import Tax


class TaxRepository(Protocol):
    async def get_by_id(self, tenant_id: str, tax_id: str) -> Tax | None: ...

    async def create(self, tax: Tax) -> Tax: ...

    async def list_active_for_tenant(self, tenant_id: str) -> list[Tax]: ...
