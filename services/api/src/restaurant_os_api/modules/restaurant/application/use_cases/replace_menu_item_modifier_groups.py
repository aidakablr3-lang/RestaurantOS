"""ReplaceMenuItemModifierGroupsUseCase.

Restaurant Platform Architecture SS7's ``PUT /api/v1/menu-items/{id}/
modifier-groups`` -- body: list of ``modifier_group_id``s, replacing
the *full* set atomically, matching how ``MenuItemModifierGroup`` is a
pure join (the same "replace, not patch" semantics
``ReplaceRolePermissionsUseCase`` already established for
``RolePermission``, itself a pure join).

``menu_item_id`` is loaded scoped to the caller's tenant first
(``MenuItemNotFoundError`` if missing/cross-tenant, the same
belt-and-suspenders discipline every other parent-scope check in this
module uses). Every ``modifier_group_id`` in the request is then
individually verified to belong to the *same* tenant before the
replace is issued -- a single invalid or cross-tenant id anywhere in
the set fails the whole call with ``ModifierGroupNotFoundError``
(no partial replace, no silently-dropped ids), preventing a caller
from using this endpoint to probe for the existence of another
tenant's modifier groups one id at a time.

``replace_for_menu_item`` itself is atomic (delete + insert inside the
same flush, inside this use case's own transaction) -- an empty
request set is valid and simply clears every attachment.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import (
    MenuItemModifierGroupsDTO,
    ReplaceMenuItemModifierGroupsRequestDTO,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuItemNotFoundError,
    ModifierGroupNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    MenuItemModifierGroupRepository,
    MenuItemRepository,
    ModifierGroupRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ReplaceMenuItemModifierGroupsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        modifier_group_repository_factory: Callable[[AsyncSession], ModifierGroupRepository],
        menu_item_modifier_group_repository_factory: Callable[
            [AsyncSession], MenuItemModifierGroupRepository
        ],
    ) -> None:
        self._session_factory = session_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._modifier_group_repository_factory = modifier_group_repository_factory
        self._menu_item_modifier_group_repository_factory = (
            menu_item_modifier_group_repository_factory
        )

    async def execute(
        self, tenant_id: str, request: ReplaceMenuItemModifierGroupsRequestDTO
    ) -> MenuItemModifierGroupsDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            modifier_group_repo = self._modifier_group_repository_factory(uow.session)
            attachment_repo = self._menu_item_modifier_group_repository_factory(uow.session)

            menu_item = await menu_item_repo.get_by_id(tenant_id, request.menu_item_id)
            if menu_item is None:
                raise MenuItemNotFoundError(request.menu_item_id)

            for modifier_group_id in request.modifier_group_ids:
                modifier_group = await modifier_group_repo.get_by_id(tenant_id, modifier_group_id)
                if modifier_group is None:
                    raise ModifierGroupNotFoundError(modifier_group_id)

            await attachment_repo.replace_for_menu_item(
                tenant_id, request.menu_item_id, request.modifier_group_ids
            )

        return MenuItemModifierGroupsDTO(
            menu_item_id=request.menu_item_id, modifier_group_ids=request.modifier_group_ids
        )
