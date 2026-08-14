"""GetInventoryItemUseCase.

**Food-vs-beverage gate:** if the item's category is
``category_type="food"``, the caller additionally needs
``inventory_food.read`` (at any scope) -- see
``create_inventory_category.py``'s module docstring for the full
rationale.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import InventoryItemDTO
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_item_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import InventoryCategoryType
from restaurant_os_api.modules.operations.domain.exceptions import InventoryItemNotFoundError
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryCategoryRepository,
    InventoryItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_FOOD_GATE_PERMISSION = "inventory_food.read"


class GetInventoryItemUseCase:
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
        self, tenant_id: str, user_id: str, branch_id: str, inventory_item_id: str
    ) -> InventoryItemDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            item_repo = self._inventory_item_repository_factory(uow.session)
            category_repo = self._inventory_category_repository_factory(uow.session)
            item = await item_repo.get_by_id(tenant_id, inventory_item_id)
            if item is None or item.branch_id != branch_id:
                raise InventoryItemNotFoundError(inventory_item_id)

            category = await category_repo.get_by_id(tenant_id, item.inventory_category_id)
            if category is not None and category.category_type is InventoryCategoryType.FOOD:
                resolved = await self._resolve_user_permissions.execute(tenant_id, user_id)
                if not resolved.has(_FOOD_GATE_PERMISSION) and not resolved.branch_ids_with(
                    _FOOD_GATE_PERMISSION
                ):
                    raise PermissionDeniedError(_FOOD_GATE_PERMISSION)
        return inventory_item_to_dto(item)
