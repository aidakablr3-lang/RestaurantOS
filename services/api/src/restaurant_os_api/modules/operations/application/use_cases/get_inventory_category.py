"""GetInventoryCategoryUseCase.

No single-category read-by-id existed anywhere in ``modules/operations``
before this (``list_inventory_categories.py`` lists a tenant's whole
catalogue; nothing took an ``inventory_category_id`` and returned one) --
added for Phase 1 design doc §A.7's ``AddInventoryStep.verify()``, which
needs to confirm the category an inventory item belongs to still exists,
not just the item itself. Same ``Get*UseCase`` convention as
``GetUserUseCase``/``GetRoleByNameUseCase``.

**Food-vs-beverage gate:** mirrors ``GetInventoryItemUseCase``'s own
rationale exactly -- a ``category_type="food"`` category additionally
requires ``inventory_food.read`` (at any scope); a ``beverage`` category
needs nothing beyond the caller already being resolvable.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import InventoryCategoryDTO
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_category_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import InventoryCategoryType
from restaurant_os_api.modules.operations.domain.exceptions import InventoryCategoryNotFoundError
from restaurant_os_api.modules.operations.domain.ports import InventoryCategoryRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_FOOD_GATE_PERMISSION = "inventory_food.read"


class GetInventoryCategoryUseCase:
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

    async def execute(
        self, tenant_id: str, user_id: str, inventory_category_id: str
    ) -> InventoryCategoryDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            category_repo = self._inventory_category_repository_factory(uow.session)
            category = await category_repo.get_by_id(tenant_id, inventory_category_id)

        if category is None:
            raise InventoryCategoryNotFoundError(inventory_category_id)

        if category.category_type is InventoryCategoryType.FOOD:
            resolved = await self._resolve_user_permissions.execute(tenant_id, user_id)
            if not resolved.has(_FOOD_GATE_PERMISSION) and not resolved.branch_ids_with(
                _FOOD_GATE_PERMISSION
            ):
                raise PermissionDeniedError(_FOOD_GATE_PERMISSION)

        return inventory_category_to_dto(category)
