"""GetMenuItemUseCase.

Restaurant Platform Architecture SS7's ``GET /api/v1/menu-categories/
{menu_category_id}/menu-items/{id}``. Same cross-category scoping
discipline as ``GetTableUseCase`` -- a menu item that exists but
belongs to a *different* category than the URL's own is
``MenuItemNotFoundError``, not a distinguishable error.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import MenuItemDTO
from restaurant_os_api.modules.restaurant.application.use_cases._menu_item_mapper import (
    menu_item_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import MenuItemRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetMenuItemUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
    ) -> None:
        self._session_factory = session_factory
        self._menu_item_repository_factory = menu_item_repository_factory

    async def execute(
        self, tenant_id: str, menu_category_id: str, menu_item_id: str
    ) -> MenuItemDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            menu_item = await menu_item_repo.get_by_id(tenant_id, menu_item_id)

        if menu_item is None or menu_item.menu_category_id != menu_category_id:
            raise MenuItemNotFoundError(menu_item_id)

        return menu_item_to_dto(menu_item)
