"""ListMenuItemsUseCase -- category-scoped, offset/limit paginated,
deterministic ordering by ``display_order``
(``MenuItemRepository.list_for_category``'s own ``ORDER BY``,
pre-existing Step 3 code, unchanged here, mirroring
``ListTablesUseCase``'s own precedent).

``menu_category_id`` is verified to exist (scoped to the caller's
tenant) before listing, mirroring ``ListTablesUseCase``'s own check.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import MenuItemListResultDTO
from restaurant_os_api.modules.restaurant.application.use_cases._menu_item_mapper import (
    menu_item_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuCategoryNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    MenuCategoryRepository,
    MenuItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListMenuItemsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
    ) -> None:
        self._session_factory = session_factory
        self._menu_category_repository_factory = menu_category_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory

    async def execute(
        self, tenant_id: str, menu_category_id: str, *, offset: int, limit: int
    ) -> MenuItemListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_category_repo = self._menu_category_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)

            menu_category = await menu_category_repo.get_by_id(tenant_id, menu_category_id)
            if menu_category is None:
                raise MenuCategoryNotFoundError(menu_category_id)

            menu_items, total = await menu_item_repo.list_for_category(
                tenant_id, menu_category_id, offset=offset, limit=limit
            )

        return MenuItemListResultDTO(
            menu_items=[menu_item_to_dto(i) for i in menu_items],
            total=total,
            offset=offset,
            limit=limit,
        )
