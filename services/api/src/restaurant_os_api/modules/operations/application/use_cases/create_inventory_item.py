"""CreateInventoryItemUseCase.

Architecture doc SS6's ``POST /api/v1/branches/{branch_id}/inventory-items``
-- branch-nested, gated at the router by ``require_branch_permission``,
mirroring ``CreateOrderUseCase``'s own shape (no extra
``resolve_and_authorize_branch`` call needed here since the router
already gated on the URL's own ``branch_id``).

**Food-vs-beverage gate:** an item filed under a ``category_type="food"``
category additionally requires ``inventory_food.manage`` (at any
scope) -- see ``create_inventory_category.py``'s module docstring for
the full rationale.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import (
    CreateInventoryItemRequestDTO,
    InventoryItemDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_item_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import (
    InventoryCategoryType,
    InventoryItem,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    InventoryCategoryNotFoundError,
    InventoryItemNameConflictError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryCategoryRepository,
    InventoryItemRepository,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_FOOD_GATE_PERMISSION = "inventory_food.manage"


class CreateInventoryItemUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        inventory_item_repository_factory: Callable[[AsyncSession], InventoryItemRepository],
        inventory_category_repository_factory: Callable[
            [AsyncSession], InventoryCategoryRepository
        ],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._inventory_item_repository_factory = inventory_item_repository_factory
        self._inventory_category_repository_factory = inventory_category_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, request: CreateInventoryItemRequestDTO
    ) -> InventoryItemDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            category_repo = self._inventory_category_repository_factory(uow.session)
            item_repo = self._inventory_item_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            category = await category_repo.get_by_id(tenant_id, request.inventory_category_id)
            if category is None:
                raise InventoryCategoryNotFoundError(request.inventory_category_id)

            if category.category_type is InventoryCategoryType.FOOD:
                resolved = await self._resolve_user_permissions.execute(tenant_id, user_id)
                if not resolved.has(_FOOD_GATE_PERMISSION) and not resolved.branch_ids_with(
                    _FOOD_GATE_PERMISSION
                ):
                    raise PermissionDeniedError(_FOOD_GATE_PERMISSION)

            existing = await item_repo.get_by_branch_id_and_name(
                tenant_id, request.branch_id, request.name
            )
            if existing is not None:
                raise InventoryItemNameConflictError(request.branch_id, request.name)

            item = await item_repo.create(
                InventoryItem(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    inventory_category_id=request.inventory_category_id,
                    name=request.name,
                    unit=request.unit,
                    quantity_on_hand=Decimal(0),
                    created_at=now,
                    reorder_point=request.reorder_point,
                    allow_negative_stock_override=request.allow_negative_stock_override,
                )
            )
        return inventory_item_to_dto(item)
