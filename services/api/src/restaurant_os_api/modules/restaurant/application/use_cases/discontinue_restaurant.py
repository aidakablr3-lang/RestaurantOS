"""DiscontinueRestaurantUseCase -- the lifecycle action Architecture
SS3.1's ``created -> active -> discontinued`` status enum defines,
mirroring ``Branch``'s own ``POST /branches/{id}/close`` sub-resource-
verb pattern (SS7). No hard-delete exists or is introduced here --
``Restaurant`` has no ``delete()`` domain method, only
``discontinue()``, which is the guarded, one-way transition this use
case calls rather than setting ``status`` directly.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import RestaurantDTO
from restaurant_os_api.modules.restaurant.application.use_cases._restaurant_mapper import (
    restaurant_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.events import RestaurantDiscontinued
from restaurant_os_api.modules.restaurant.domain.exceptions import RestaurantNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import RestaurantRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class DiscontinueRestaurantUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._restaurant_repository_factory = restaurant_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, restaurant_id: str) -> RestaurantDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            restaurant = await restaurant_repo.get_by_id(tenant_id, restaurant_id)
            if restaurant is None:
                raise RestaurantNotFoundError(restaurant_id)

            restaurant.discontinue()
            restaurant = await restaurant_repo.update(restaurant)

            await outbox.publish(
                tenant_id,
                RestaurantDiscontinued(restaurant_id=restaurant.id, occurred_at=now),
            )

        return restaurant_to_dto(restaurant)
