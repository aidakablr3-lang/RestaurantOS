"""ListRestaurantsUseCase -- tenant-scoped, offset/limit paginated,
deterministic ordering (``RestaurantRepository.list_for_tenant``
orders by ``created_at DESC``, matching every other paginated list in
this codebase -- ``BranchRepository.list_for_restaurant``,
``RoleRepository.list_for_tenant``)."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import RestaurantListResultDTO
from restaurant_os_api.modules.restaurant.application.use_cases._restaurant_mapper import (
    restaurant_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.ports import RestaurantRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListRestaurantsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
    ) -> None:
        self._session_factory = session_factory
        self._restaurant_repository_factory = restaurant_repository_factory

    async def execute(self, tenant_id: str, *, offset: int, limit: int) -> RestaurantListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            restaurants, total = await restaurant_repo.list_for_tenant(
                tenant_id, offset=offset, limit=limit
            )
        return RestaurantListResultDTO(
            restaurants=[restaurant_to_dto(r) for r in restaurants],
            total=total,
            offset=offset,
            limit=limit,
        )
