"""UpdateInventoryItemUseCase.

Branch-nested ``PATCH /api/v1/branches/{branch_id}/inventory-items/{id}``.
Full-replace over the editable fields (``name``, ``inventory_category_id``,
``reorder_point``, ``allow_negative_stock_override``) -- never touches
``quantity_on_hand``, which stays exclusively trigger-maintained.

**Food-vs-beverage gate:** if the item's current category, or the
category it's being moved to, is ``category_type="food"``, the caller
additionally needs ``inventory_food.manage`` (at any scope) -- see
``create_inventory_category.py``'s module docstring for the full
rationale. Checking both sides closes the obvious workaround (moving a
food item OUT of a food category, or a beverage item INTO one, without
the permission that same move would otherwise require).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import (
    InventoryItemDTO,
    UpdateInventoryItemRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_item_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import InventoryCategoryType
from restaurant_os_api.modules.operations.domain.exceptions import (
    InventoryCategoryNotFoundError,
    InventoryItemNameConflictError,
    InventoryItemNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryCategoryRepository,
    InventoryItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_FOOD_GATE_PERMISSION = "inventory_food.manage"


class UpdateInventoryItemUseCase:
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
        self, tenant_id: str, user_id: str, branch_id: str, request: UpdateInventoryItemRequestDTO
    ) -> InventoryItemDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            item_repo = self._inventory_item_repository_factory(uow.session)
            category_repo = self._inventory_category_repository_factory(uow.session)

            item = await item_repo.get_by_id(tenant_id, request.inventory_item_id)
            if item is None or item.branch_id != branch_id:
                raise InventoryItemNotFoundError(request.inventory_item_id)

            current_category = await category_repo.get_by_id(
                tenant_id, item.inventory_category_id
            )
            touches_food = (
                current_category is not None
                and current_category.category_type is InventoryCategoryType.FOOD
            )

            if request.inventory_category_id != item.inventory_category_id:
                category = await category_repo.get_by_id(tenant_id, request.inventory_category_id)
                if category is None:
                    raise InventoryCategoryNotFoundError(request.inventory_category_id)
                touches_food = touches_food or category.category_type is InventoryCategoryType.FOOD

            if touches_food:
                resolved = await self._resolve_user_permissions.execute(tenant_id, user_id)
                if not resolved.has(_FOOD_GATE_PERMISSION) and not resolved.branch_ids_with(
                    _FOOD_GATE_PERMISSION
                ):
                    raise PermissionDeniedError(_FOOD_GATE_PERMISSION)

            if request.name != item.name:
                existing = await item_repo.get_by_branch_id_and_name(
                    tenant_id, branch_id, request.name
                )
                if existing is not None:
                    raise InventoryItemNameConflictError(branch_id, request.name)

            item.name = request.name
            item.inventory_category_id = request.inventory_category_id
            item.reorder_point = request.reorder_point
            item.allow_negative_stock_override = request.allow_negative_stock_override
            item = await item_repo.update(item)
        return inventory_item_to_dto(item)
