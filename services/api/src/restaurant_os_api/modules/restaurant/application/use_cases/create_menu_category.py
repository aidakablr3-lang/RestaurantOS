"""CreateMenuCategoryUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/restaurants/
{restaurant_id}/menu-categories``. ``restaurant_id`` is loaded scoped
to the caller's own tenant before anything else -- a restaurant that
exists but belongs to another tenant is treated identically to one
that does not exist at all (``RestaurantNotFoundError``, never a
distinguishable 403), the same "belt and suspenders" pattern
``CreateTableZoneUseCase`` already established for its own
parent-scope check against ``branch_id``.

Publishes ``MenuCategoryCreated`` (SS11's event catalogue names this
event explicitly).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateMenuCategoryRequestDTO,
    MenuCategoryDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._menu_category_mapper import (
    menu_category_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import MenuCategory
from restaurant_os_api.modules.restaurant.domain.events import MenuCategoryCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuCategoryNameConflictError,
    RestaurantNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    MenuCategoryRepository,
    RestaurantRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateMenuCategoryUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._restaurant_repository_factory = restaurant_repository_factory
        self._menu_category_repository_factory = menu_category_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, request: CreateMenuCategoryRequestDTO
    ) -> MenuCategoryDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            menu_category_repo = self._menu_category_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            restaurant = await restaurant_repo.get_by_id(tenant_id, request.restaurant_id)
            if restaurant is None:
                raise RestaurantNotFoundError(request.restaurant_id)

            existing = await menu_category_repo.get_by_restaurant_id_and_name(
                tenant_id, request.restaurant_id, request.name
            )
            if existing is not None:
                raise MenuCategoryNameConflictError(request.restaurant_id, request.name)

            menu_category = await menu_category_repo.create(
                MenuCategory(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    restaurant_id=request.restaurant_id,
                    name=request.name,
                    display_order=request.display_order,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                MenuCategoryCreated(
                    menu_category_id=menu_category.id,
                    restaurant_id=menu_category.restaurant_id,
                    name=menu_category.name,
                    occurred_at=now,
                ),
            )

        return menu_category_to_dto(menu_category)
