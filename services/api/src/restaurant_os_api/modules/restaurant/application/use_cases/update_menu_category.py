"""UpdateMenuCategoryUseCase.

Restaurant Platform Architecture SS7's ``PATCH /api/v1/restaurants/
{restaurant_id}/menu-categories/{id}``. Both ``name`` and
``display_order`` are editable here in one call -- SS8's Menu
Management screen lists "Create, edit, reorder" as one action set,
mirroring ``UpdateTableZoneUseCase``'s own precedent exactly.

Same cross-restaurant scoping discipline as ``GetMenuCategoryUseCase``:
a menu category belonging to a different restaurant than the URL's own
is ``MenuCategoryNotFoundError``, not a distinguishable error.

No domain event is published -- Architecture SS11's event catalogue
names only ``MenuCategoryCreated``, no ``MenuCategoryUpdated``
counterpart (matching ``TableZone``'s own precedent), so none is
invented here.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import (
    MenuCategoryDTO,
    UpdateMenuCategoryRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._menu_category_mapper import (
    menu_category_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuCategoryNameConflictError,
    MenuCategoryNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import MenuCategoryRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateMenuCategoryUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
    ) -> None:
        self._session_factory = session_factory
        self._menu_category_repository_factory = menu_category_repository_factory

    async def execute(
        self, tenant_id: str, request: UpdateMenuCategoryRequestDTO
    ) -> MenuCategoryDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_category_repo = self._menu_category_repository_factory(uow.session)

            menu_category = await menu_category_repo.get_by_id(tenant_id, request.menu_category_id)
            if menu_category is None or menu_category.restaurant_id != request.restaurant_id:
                raise MenuCategoryNotFoundError(request.menu_category_id)

            if request.name != menu_category.name:
                existing = await menu_category_repo.get_by_restaurant_id_and_name(
                    tenant_id, menu_category.restaurant_id, request.name
                )
                if existing is not None and existing.id != menu_category.id:
                    raise MenuCategoryNameConflictError(menu_category.restaurant_id, request.name)
                menu_category.name = request.name

            menu_category.display_order = request.display_order

            menu_category = await menu_category_repo.update(menu_category)

        return menu_category_to_dto(menu_category)
