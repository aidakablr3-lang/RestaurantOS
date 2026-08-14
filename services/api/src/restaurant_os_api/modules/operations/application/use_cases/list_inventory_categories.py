"""ListInventoryCategoriesUseCase. ``GET /api/v1/inventory-categories``.

Filters out ``category_type="food"`` categories for a caller who
doesn't hold ``inventory_food.read`` -- see
``create_inventory_category.py``'s module docstring for the full
food-vs-beverage gate rationale. A small, single-tenant list (no
pagination on this endpoint), so filtering the already-fetched list in
Python is both correct and simple -- no need for a SQL-level filter the
way ``list_inventory_items.py`` needs for its paginated query.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import InventoryCategoryListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_category_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import InventoryCategoryType
from restaurant_os_api.modules.operations.domain.ports import InventoryCategoryRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_FOOD_GATE_PERMISSION = "inventory_food.read"


class ListInventoryCategoriesUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        inventory_category_repository_factory: Callable[
            [AsyncSession], InventoryCategoryRepository
        ],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._inventory_category_repository_factory = inventory_category_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(self, tenant_id: str, user_id: str) -> InventoryCategoryListResultDTO:
        resolved = await self._resolve_user_permissions.execute(tenant_id, user_id)
        can_see_food = bool(
            resolved.has(_FOOD_GATE_PERMISSION) or resolved.branch_ids_with(_FOOD_GATE_PERMISSION)
        )

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            category_repo = self._inventory_category_repository_factory(uow.session)
            categories = await category_repo.list_for_tenant(tenant_id)

        if not can_see_food:
            categories = [
                c for c in categories if c.category_type is not InventoryCategoryType.FOOD
            ]

        return InventoryCategoryListResultDTO(
            categories=[inventory_category_to_dto(c) for c in categories]
        )
