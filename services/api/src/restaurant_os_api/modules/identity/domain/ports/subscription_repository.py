"""Repository port for Subscription."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import Subscription


class SubscriptionRepository(Protocol):
    async def get_by_tenant_id(self, tenant_id: str) -> Subscription | None: ...

    async def create(self, subscription: Subscription) -> Subscription: ...

    async def update(self, subscription: Subscription) -> Subscription: ...
