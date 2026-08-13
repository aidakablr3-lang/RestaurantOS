"""Repository port for Restaurant."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import Restaurant


class RestaurantRepository(Protocol):
    async def get_by_id(self, tenant_id: str, restaurant_id: str) -> Restaurant | None: ...

    async def create(self, restaurant: Restaurant) -> Restaurant: ...

    async def update(self, restaurant: Restaurant) -> Restaurant: ...

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Restaurant], int]:
        """Returns (restaurants, total_count) -- offset/limit pagination
        (Technical Architecture v2.0 SS5.7)."""
        ...
