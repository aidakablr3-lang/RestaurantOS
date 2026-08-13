"""GetMenuCategoryUseCase.

Restaurant Platform Architecture SS7's ``GET /api/v1/restaurants/
{restaurant_id}/menu-categories/{id}``. The route is nested under a
specific restaurant (so ``require_permission`` gates tenant-wide, and
the use case itself scopes to the URL's own ``restaurant_id``) -- a
menu category that exists but belongs to a *different* restaurant than
the URL's own must be treated identically to one that does not exist
at all, the same "belt and suspenders" scoping discipline
``GetTableZoneUseCase`` already established one level down for
cross-branch access within the same tenant.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import MenuCategoryDTO
from restaurant_os_api.modules.restaurant.application.use_cases._menu_category_mapper import (
    menu_category_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuCategoryNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import MenuCategoryRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetMenuCategoryUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
    ) -> None:
        self._session_factory = session_factory
        self._menu_category_repository_factory = menu_category_repository_factory

    async def execute(
        self, tenant_id: str, restaurant_id: str, menu_category_id: str
    ) -> MenuCategoryDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_category_repo = self._menu_category_repository_factory(uow.session)
            menu_category = await menu_category_repo.get_by_id(tenant_id, menu_category_id)

        if menu_category is None or menu_category.restaurant_id != restaurant_id:
            raise MenuCategoryNotFoundError(menu_category_id)

        return menu_category_to_dto(menu_category)
