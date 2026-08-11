"""Repository port for Supplier."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import Supplier


class SupplierRepository(Protocol):
    async def get_by_id(self, tenant_id: str, supplier_id: str) -> Supplier | None: ...

    async def get_by_tenant_id_and_name(self, tenant_id: str, name: str) -> Supplier | None: ...

    async def create(self, supplier: Supplier) -> Supplier: ...

    async def update(self, supplier: Supplier) -> Supplier: ...

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Supplier], int]: ...
