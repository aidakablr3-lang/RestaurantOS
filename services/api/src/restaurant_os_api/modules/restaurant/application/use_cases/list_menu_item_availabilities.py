"""ListMenuItemAvailabilitiesUseCase -- the availability-dimension
twin of ``ListMenuItemBranchPricesUseCase``, identical
tenant-wide-vs-branch-scoped filtering (see that use case's own
docstring for the full reasoning)."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.restaurant.application.dto import MenuItemAvailabilityDTO
from restaurant_os_api.modules.restaurant.application.use_cases._menu_item_availability_mapper import (
    menu_item_availability_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    MenuItemAvailabilityRepository,
    MenuItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "menu.read"


class ListMenuItemAvailabilitiesUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        menu_item_availability_repository_factory: Callable[
            [AsyncSession], MenuItemAvailabilityRepository
        ],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._menu_item_availability_repository_factory = menu_item_availability_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, menu_item_id: str
    ) -> list[MenuItemAvailabilityDTO]:
        resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            availability_repo = self._menu_item_availability_repository_factory(uow.session)

            menu_item = await menu_item_repo.get_by_id(tenant_id, menu_item_id)
            if menu_item is None:
                raise MenuItemNotFoundError(menu_item_id)

            rows = await availability_repo.list_for_menu_item(tenant_id, menu_item_id)

        if PERMISSION_CODE in resolved_permissions.tenant_wide:
            visible = rows
        else:
            accessible_branch_ids = resolved_permissions.branch_ids_with(PERMISSION_CODE)
            visible = [r for r in rows if r.branch_id in accessible_branch_ids]

        return [menu_item_availability_to_dto(r) for r in visible]
