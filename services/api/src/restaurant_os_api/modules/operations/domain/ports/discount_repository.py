"""Repository port for Discount."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import Discount


class DiscountRepository(Protocol):
    async def get_by_id(self, tenant_id: str, discount_id: str) -> Discount | None: ...

    async def create(self, discount: Discount) -> Discount: ...

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Discount], int]: ...
