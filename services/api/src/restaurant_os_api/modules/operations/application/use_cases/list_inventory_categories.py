"""ListInventoryCategoriesUseCase. ``GET /api/v1/inventory-categories``."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import InventoryCategoryListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_category_to_dto,
)
from restaurant_os_api.modules.operations.domain.ports import InventoryCategoryRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListInventoryCategoriesUseCase:
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

    async def execute(self, tenant_id: str) -> InventoryCategoryListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            category_repo = self._inventory_category_repository_factory(uow.session)
            categories = await category_repo.list_for_tenant(tenant_id)
        return InventoryCategoryListResultDTO(
            categories=[inventory_category_to_dto(c) for c in categories]
        )
