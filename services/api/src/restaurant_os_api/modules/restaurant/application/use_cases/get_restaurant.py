"""GetRestaurantUseCase."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import RestaurantDTO
from restaurant_os_api.modules.restaurant.application.use_cases._restaurant_mapper import (
    restaurant_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import RestaurantNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import RestaurantRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetRestaurantUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
    ) -> None:
        self._session_factory = session_factory
        self._restaurant_repository_factory = restaurant_repository_factory

    async def execute(self, tenant_id: str, restaurant_id: str) -> RestaurantDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            restaurant = await restaurant_repo.get_by_id(tenant_id, restaurant_id)
        if restaurant is None:
            raise RestaurantNotFoundError(restaurant_id)
        return restaurant_to_dto(restaurant)
