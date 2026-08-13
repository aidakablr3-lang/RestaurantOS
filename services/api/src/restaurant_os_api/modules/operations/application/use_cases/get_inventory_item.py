"""GetInventoryItemUseCase."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import InventoryItemDTO
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    inventory_item_to_dto,
)
from restaurant_os_api.modules.operations.domain.exceptions import InventoryItemNotFoundError
from restaurant_os_api.modules.operations.domain.ports import InventoryItemRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetInventoryItemUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        inventory_item_repository_factory: Callable[[AsyncSession], InventoryItemRepository],
    ) -> None:
        self._session_factory = session_factory
        self._inventory_item_repository_factory = inventory_item_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, inventory_item_id: str
    ) -> InventoryItemDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            item_repo = self._inventory_item_repository_factory(uow.session)
            item = await item_repo.get_by_id(tenant_id, inventory_item_id)
            if item is None or item.branch_id != branch_id:
                raise InventoryItemNotFoundError(inventory_item_id)
        return inventory_item_to_dto(item)
