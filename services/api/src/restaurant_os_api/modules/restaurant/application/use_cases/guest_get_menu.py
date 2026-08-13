"""GuestGetMenuUseCase.

Backs ``GET /api/v1/qr/{token}/menu`` (guest ordering, full-day
operational simulation gap fix) -- the first genuinely new public read
path this codebase has added since ADR 0001 drew the line at resolution
alone. Takes an already-resolved ``branch_id`` (the router resolves the
QR token first, the same "resolution is a bootstrap step, never
authorization by itself" discipline every other guest use case in this
feature follows) and returns only what a guest needs to order:
available items, grouped by category, in display order. Unavailable
items (``is_available=False``) are filtered out entirely, never
returned with a disabled/greyed marker -- a guest has no use for an
item they cannot order, unlike the authenticated menu-management UI
which needs to show unavailable items to let staff re-enable them.

No branch-price/availability-override resolution -- the same disclosed
scope-narrowing ``AddOrderItemUseCase`` already carries forward
(``price_amount`` is the base ``MenuItem`` price, not a resolved
per-branch effective price; nothing in this codebase provides that
resolution as a reusable helper yet).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import (
    GuestMenuCategoryDTO,
    GuestMenuDTO,
    GuestMenuItemDTO,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    RestaurantNotFoundError,
    TableNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    MenuCategoryRepository,
    MenuItemRepository,
    RestaurantRepository,
    TableRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_MAX_CATEGORIES = 200
_MAX_ITEMS_PER_CATEGORY = 500


class GuestGetMenuUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        menu_category_repository_factory: Callable[[AsyncSession], MenuCategoryRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._restaurant_repository_factory = restaurant_repository_factory
        self._table_repository_factory = table_repository_factory
        self._menu_category_repository_factory = menu_category_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory

    async def execute(self, tenant_id: str, branch_id: str, table_id: str) -> GuestMenuDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)
            menu_category_repo = self._menu_category_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, branch_id)
            if branch is None:
                raise BranchNotFoundError(branch_id)

            restaurant = await restaurant_repo.get_by_id(tenant_id, branch.restaurant_id)
            if restaurant is None:
                raise RestaurantNotFoundError(branch.restaurant_id)

            table = await table_repo.get_by_id(tenant_id, table_id)
            if table is None:
                raise TableNotFoundError(table_id)

            categories, _ = await menu_category_repo.list_for_restaurant(
                tenant_id, branch.restaurant_id, offset=0, limit=_MAX_CATEGORIES
            )
            categories = sorted(categories, key=lambda c: c.display_order)

            category_dtos: list[GuestMenuCategoryDTO] = []
            for category in categories:
                items, _ = await menu_item_repo.list_for_category(
                    tenant_id, category.id, offset=0, limit=_MAX_ITEMS_PER_CATEGORY
                )
                available_items = sorted(
                    (item for item in items if item.is_available),
                    key=lambda i: i.display_order,
                )
                if not available_items:
                    continue
                category_dtos.append(
                    GuestMenuCategoryDTO(
                        id=category.id,
                        name=category.name,
                        display_order=category.display_order,
                        items=[
                            GuestMenuItemDTO(
                                id=item.id,
                                name=item.name,
                                price_amount=item.price_amount,
                                currency_code=item.currency_code,
                            )
                            for item in available_items
                        ],
                    )
                )

        return GuestMenuDTO(
            branch_id=branch_id,
            table_id=table_id,
            restaurant_name=restaurant.display_name,
            branch_name=branch.name,
            table_number=table.table_number,
            categories=category_dtos,
        )
