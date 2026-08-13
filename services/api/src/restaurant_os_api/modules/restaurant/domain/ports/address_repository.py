"""Repository port for Address."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import Address


class AddressRepository(Protocol):
    async def get_by_id(self, tenant_id: str, address_id: str) -> Address | None: ...

    async def create(self, address: Address) -> Address: ...

    async def update(self, address: Address) -> Address: ...
