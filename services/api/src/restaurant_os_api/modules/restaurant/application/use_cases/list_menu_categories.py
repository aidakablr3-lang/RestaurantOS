"""ListMenuCategoriesUseCase -- restaurant-scoped, offset/limit
paginated, deterministic ordering by ``display_order``
(``MenuCategoryRepository.list_for_restaurant`` -- the "reorder"
action SS8's Menu Management screen names is exactly re-saving each
row's ``display_order`` via ``PATCH``, read back here in that same
order, mirroring ``ListTableZonesUseCase``'s own precedent).

``restaurant_id`` is verified to exist (scoped to the caller's tenant)
before listing, mirroring ``ListTableZonesUseCase``'s own check -- an
unknown or cross-tenant restaurant is ``RestaurantNotFoundError``, not
an empty list.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import MenuCategoryListResultDTO
from restaurant_os_api.modules.restaurant.application.use_cases._menu_category_mapper import (
    menu_category_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import RestaurantNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    MenuCategoryRepository,
    RestaurantRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListMenuCategoriesUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
    ) -> None:
        self._session_factory = session_factory
        self._restaurant_repository_factory = restaurant_repository_factory
        self._menu_category_repository_factory = menu_category_repository_factory

    async def execute(
        self, tenant_id: str, restaurant_id: str, *, offset: int, limit: int
    ) -> MenuCategoryListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            menu_category_repo = self._menu_category_repository_factory(uow.session)

            restaurant = await restaurant_repo.get_by_id(tenant_id, restaurant_id)
            if restaurant is None:
                raise RestaurantNotFoundError(restaurant_id)

            menu_categories, total = await menu_category_repo.list_for_restaurant(
                tenant_id, restaurant_id, offset=offset, limit=limit
            )

        return MenuCategoryListResultDTO(
            menu_categories=[menu_category_to_dto(c) for c in menu_categories],
            total=total,
            offset=offset,
            limit=limit,
        )
