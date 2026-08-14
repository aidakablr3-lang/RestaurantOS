"""CreateInventoryCategoryUseCase. ``POST /api/v1/inventory-categories``
-- tenant-wide, mirrors ``CreateDiscountUseCase``'s own shape.

**Food-vs-beverage gate (2026-08-14 product decision):** recipe-based
food-inventory deduction can't be trusted to reflect real chef usage,
so day-to-day food inventory tracking is being de-scoped from the
default "Inventory Manager" workflow -- liquor/beverage inventory stays
fully tracked. Rather than hardcoding that role by name (RBAC
throughout this codebase is deliberately permission-based, never
role-name-based -- a tenant can rename or replace the role), a
``category_type="food"`` category additionally requires the dedicated
``inventory_food.manage`` (at any scope) beyond the ``inventory.manage``
the router already gates on -- NOT ``menu.manage``, since the real
seeded "Inventory Manager" role already holds that one for recipe
editing and reusing it would restrict nothing. Restaurant Manager and
Tenant Owner hold ``inventory_food.manage`` by default; Inventory
Manager does not. A ``beverage`` category needs nothing beyond the
existing ``inventory.manage`` gate.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import (
    CreateInventoryCategoryRequestDTO,
    InventoryCategoryDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_category_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import (
    InventoryCategory,
    InventoryCategoryType,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    InventoryCategoryNameConflictError,
)
from restaurant_os_api.modules.operations.domain.ports import InventoryCategoryRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_FOOD_GATE_PERMISSION = "inventory_food.manage"


class CreateInventoryCategoryUseCase:
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
        self, tenant_id: str, user_id: str, request: CreateInventoryCategoryRequestDTO
    ) -> InventoryCategoryDTO:
        category_type = InventoryCategoryType(request.category_type)
        if category_type is InventoryCategoryType.FOOD:
            resolved = await self._resolve_user_permissions.execute(tenant_id, user_id)
            if not resolved.has(_FOOD_GATE_PERMISSION) and not resolved.branch_ids_with(
                _FOOD_GATE_PERMISSION
            ):
                raise PermissionDeniedError(_FOOD_GATE_PERMISSION)

        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            category_repo = self._inventory_category_repository_factory(uow.session)
            existing = await category_repo.get_by_tenant_id_and_name(tenant_id, request.name)
            if existing is not None:
                raise InventoryCategoryNameConflictError(request.name)

            category = await category_repo.create(
                InventoryCategory(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    name=request.name,
                    category_type=category_type,
                    created_at=now,
                )
            )
        return inventory_category_to_dto(category)
