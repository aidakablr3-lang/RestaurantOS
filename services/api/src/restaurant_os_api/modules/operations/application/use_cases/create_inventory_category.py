"""CreateInventoryCategoryUseCase. ``POST /api/v1/inventory-categories``
-- tenant-wide, mirrors ``CreateDiscountUseCase``'s own shape."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import (
    CreateInventoryCategoryRequestDTO,
    InventoryCategoryDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_category_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import InventoryCategory
from restaurant_os_api.modules.operations.domain.exceptions import (
    InventoryCategoryNameConflictError,
)
from restaurant_os_api.modules.operations.domain.ports import InventoryCategoryRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class CreateInventoryCategoryUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        inventory_category_repository_factory: Callable[
            [AsyncSession], InventoryCategoryRepository
        ],
    ) -> None:
        self._session_factory = session_factory
        self._inventory_category_repository_factory = inventory_category_repository_factory

    async def execute(
        self, tenant_id: str, request: CreateInventoryCategoryRequestDTO
    ) -> InventoryCategoryDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            category_repo = self._inventory_category_repository_factory(uow.session)
            existing = await category_repo.get_by_tenant_id_and_name(tenant_id, request.name)
            if existing is not None:
                raise InventoryCategoryNameConflictError(request.name)

            category = await category_repo.create(
                InventoryCategory(
                    id=generate_ulid(), tenant_id=tenant_id, name=request.name, created_at=now
                )
            )
        return inventory_category_to_dto(category)
