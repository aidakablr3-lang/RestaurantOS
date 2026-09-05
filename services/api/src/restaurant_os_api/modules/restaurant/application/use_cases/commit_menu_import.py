"""CommitMenuImportUseCase.

One transaction: resolve every row's category (case-insensitive exact
match against the restaurant's existing categories, else create it),
then create every item. All-or-nothing -- a bad row fails the whole
commit, never a half-imported menu.

Category matching is exact (case-insensitive), never fuzzy, here at
commit time. Fuzzy "did you mean 'Veg Starters'?" suggestions are a
review-grid concern (client-side, against the same list of existing
categories fetched via the ordinary list-categories endpoint) so the
owner explicitly accepts a suggestion or doesn't -- this use case never
silently merges two category names it merely thinks are similar.

``portion_label`` is folded into the persisted item name here
("Chicken Kebab — Half") -- see ``menu_import_dto``'s module docstring
for why there is no dedicated column for it yet.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import (
    CommitMenuImportRequestDTO,
    CommitMenuImportResultDTO,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    MenuCategory,
    MenuItem,
    MenuItemStation,
)
from restaurant_os_api.modules.restaurant.domain.events import MenuCategoryCreated, MenuItemCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuImportInvalidRowError,
    RestaurantNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    MenuCategoryRepository,
    MenuItemRepository,
    RestaurantRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

_CATEGORY_LIST_PAGE_SIZE = 1000


def _item_name(name: str, portion_label: str | None) -> str:
    return f"{name} — {portion_label}" if portion_label else name


class CommitMenuImportUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._restaurant_repository_factory = restaurant_repository_factory
        self._menu_category_repository_factory = menu_category_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, request: CommitMenuImportRequestDTO
    ) -> CommitMenuImportResultDTO:
        for index, row in enumerate(request.rows):
            if not row.category.strip():
                raise MenuImportInvalidRowError(index, "category is required")
            if not row.name.strip():
                raise MenuImportInvalidRowError(index, "item name is required")
            if row.price_amount <= 0:
                raise MenuImportInvalidRowError(index, "price must be greater than zero")

        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            menu_category_repo = self._menu_category_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            restaurant = await restaurant_repo.get_by_id(tenant_id, request.restaurant_id)
            if restaurant is None:
                raise RestaurantNotFoundError(request.restaurant_id)

            existing_categories, _ = await menu_category_repo.list_for_restaurant(
                tenant_id, request.restaurant_id, offset=0, limit=_CATEGORY_LIST_PAGE_SIZE
            )
            category_by_lower_name: dict[str, MenuCategory] = {
                c.name.strip().lower(): c for c in existing_categories
            }
            next_display_order = max((c.display_order for c in existing_categories), default=-1) + 1

            categories_created = 0
            items_created = 0

            for row in request.rows:
                lower_name = row.category.strip().lower()
                category = category_by_lower_name.get(lower_name)
                if category is None:
                    category = await menu_category_repo.create(
                        MenuCategory(
                            id=generate_ulid(),
                            tenant_id=tenant_id,
                            restaurant_id=request.restaurant_id,
                            name=row.category.strip(),
                            display_order=next_display_order,
                            created_at=now,
                        )
                    )
                    next_display_order += 1
                    category_by_lower_name[lower_name] = category
                    categories_created += 1
                    await outbox.publish(
                        tenant_id,
                        MenuCategoryCreated(
                            menu_category_id=category.id,
                            restaurant_id=category.restaurant_id,
                            name=category.name,
                            occurred_at=now,
                        ),
                    )

                item = await menu_item_repo.create(
                    MenuItem(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        menu_category_id=category.id,
                        name=_item_name(row.name.strip(), row.portion_label),
                        price_amount=row.price_amount,
                        currency_code=restaurant.default_currency_code,
                        is_available=True,
                        display_order=0,
                        created_at=now,
                        station=MenuItemStation.KITCHEN,
                    )
                )
                items_created += 1
                await outbox.publish(
                    tenant_id,
                    MenuItemCreated(
                        menu_item_id=item.id,
                        menu_category_id=item.menu_category_id,
                        name=item.name,
                        price_amount=item.price_amount,
                        occurred_at=now,
                    ),
                )

        return CommitMenuImportResultDTO(
            categories_created=categories_created, items_created=items_created
        )
