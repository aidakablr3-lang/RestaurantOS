"""ListInventoryItemsUseCase.

**Food-vs-beverage gate:** a caller without ``inventory_food.read``
(at any scope) never sees items filed under a ``category_type="food"``
category -- see ``create_inventory_category.py``'s module docstring for
the full rationale. Filtered at the SQL level (via
``list_for_branch``'s ``exclude_category_ids``), not after the fact in
Python, so ``offset``/``limit``/``total`` stay correct against the
paginated query itself rather than drifting once hidden rows are
dropped from an already-paginated page.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import InventoryItemListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_item_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import InventoryCategoryType
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryCategoryRepository,
    InventoryItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_FOOD_GATE_PERMISSION = "inventory_food.read"


class ListInventoryItemsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        inventory_item_repository_factory: Callable[[AsyncSession], InventoryItemRepository],
        inventory_category_repository_factory: Callable[
            [AsyncSession], InventoryCategoryRepository
        ],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._inventory_item_repository_factory = inventory_item_repository_factory
        self._inventory_category_repository_factory = inventory_category_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, branch_id: str, *, offset: int, limit: int
    ) -> InventoryItemListResultDTO:
        resolved = await self._resolve_user_permissions.execute(tenant_id, user_id)
        can_see_food = bool(
            resolved.has(_FOOD_GATE_PERMISSION) or resolved.branch_ids_with(_FOOD_GATE_PERMISSION)
        )

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            item_repo = self._inventory_item_repository_factory(uow.session)
            exclude_category_ids: frozenset[str] = frozenset()
            if not can_see_food:
                category_repo = self._inventory_category_repository_factory(uow.session)
                categories = await category_repo.list_for_tenant(tenant_id)
                exclude_category_ids = frozenset(
                    c.id for c in categories if c.category_type is InventoryCategoryType.FOOD
                )

            items, total = await item_repo.list_for_branch(
                tenant_id,
                branch_id,
                offset=offset,
                limit=limit,
                exclude_category_ids=exclude_category_ids,
            )
            dtos = [inventory_item_to_dto(i) for i in items]
        return InventoryItemListResultDTO(items=dtos, total=total, offset=offset, limit=limit)
