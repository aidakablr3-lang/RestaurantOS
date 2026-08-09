"""CreateMenuItemUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/menu-categories/
{id}/menu-items``. ``menu_category_id`` is loaded scoped to the
caller's own tenant first -- a menu category that exists but belongs
to another tenant is treated identically to one that does not exist at
all (``MenuCategoryNotFoundError``, never a distinguishable 403), the
same "belt and suspenders" pattern ``CreateTableUseCase`` already
established for its own parent-scope check against ``table_zone_id``.

No name-uniqueness check -- Architecture SS3.1's own ``MenuItem`` entry
is explicit that a duplicate name within a category is not
hard-constrained ("judged unlikely to matter enough"), unlike
``MenuCategory``/``Branch``/``TableZone``/``Table``, which each have a
real ``UNIQUE`` constraint to mirror.

``recipe_id`` is never set here -- Architecture SS3.1 names it a
reserved, unpopulated FK target for the future Inventory Platform;
nothing in this step's approved scope creates a ``Recipe`` for it to
point at.

Publishes ``MenuItemCreated`` (SS11 names this event explicitly).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateMenuItemRequestDTO,
    MenuItemDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._menu_item_mapper import (
    menu_item_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import MenuItem
from restaurant_os_api.modules.restaurant.domain.events import MenuItemCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuCategoryNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    MenuCategoryRepository,
    MenuItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateMenuItemUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._menu_category_repository_factory = menu_category_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: CreateMenuItemRequestDTO) -> MenuItemDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_category_repo = self._menu_category_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            menu_category = await menu_category_repo.get_by_id(tenant_id, request.menu_category_id)
            if menu_category is None:
                raise MenuCategoryNotFoundError(request.menu_category_id)

            menu_item = await menu_item_repo.create(
                MenuItem(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    menu_category_id=request.menu_category_id,
                    name=request.name,
                    price_amount=request.price_amount,
                    currency_code=request.currency_code,
                    is_available=request.is_available,
                    display_order=request.display_order,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                MenuItemCreated(
                    menu_item_id=menu_item.id,
                    menu_category_id=menu_item.menu_category_id,
                    name=menu_item.name,
                    price_amount=menu_item.price_amount,
                    occurred_at=now,
                ),
            )

        return menu_item_to_dto(menu_item)
