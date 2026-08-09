"""UpdateMenuItemUseCase.

Restaurant Platform Architecture SS7's ``PATCH /api/v1/menu-categories/
{menu_category_id}/menu-items/{id}``.

Same cross-category scoping discipline as ``GetMenuItemUseCase``: a
menu item belonging to a different category than the URL's own is
``MenuItemNotFoundError``, not a distinguishable error. Unlike
``Table`` (which denormalizes a stable ``branch_id`` separate from its
movable ``table_zone_id``, letting ``UpdateTableUseCase`` re-verify a
*new* zone within the same, unchanging branch), ``MenuItem`` has only
one parent-reference column, ``menu_category_id`` -- the same column
the URL segment scopes by. There is no second, stable field to hold a
"current category" distinct from "the category being moved to", and
this step's approved routes carry only one category segment in the
URL. Moving an item to a different category is therefore not offered
by this endpoint -- ``menu_category_id`` is scope, not an editable
field, exactly like ``branch_id`` is scope (never reassigned) on
``UpdateTableUseCase``.

Publishes ``MenuItemUpdated`` on every field change, including
``is_available`` -- Architecture SS11 also names a distinct
``MenuItemAvailabilityChanged`` event, but that event is tied to the
branch-scoped ``MenuItemAvailability`` override table, which is
explicitly out of this step's approved scope; toggling the base
entity's own global ``is_available`` flag is an ordinary field edit,
published exactly like ``TableUpdated`` covers all of ``Table``'s own
non-status field changes in one event.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import (
    MenuItemDTO,
    UpdateMenuItemRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._menu_item_mapper import (
    menu_item_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.events import MenuItemUpdated
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import MenuItemRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateMenuItemUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: UpdateMenuItemRequestDTO) -> MenuItemDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            menu_item = await menu_item_repo.get_by_id(tenant_id, request.menu_item_id)
            if menu_item is None or menu_item.menu_category_id != request.menu_category_id:
                raise MenuItemNotFoundError(request.menu_item_id)

            menu_item.name = request.name
            menu_item.price_amount = request.price_amount
            menu_item.currency_code = request.currency_code
            menu_item.is_available = request.is_available
            menu_item.display_order = request.display_order

            menu_item = await menu_item_repo.update(menu_item)

            await outbox.publish(
                tenant_id, MenuItemUpdated(menu_item_id=menu_item.id, occurred_at=now)
            )

        return menu_item_to_dto(menu_item)
