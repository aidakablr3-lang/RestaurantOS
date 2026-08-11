"""ListStockMovementsUseCase.

Flat ``GET /api/v1/inventory-items/{id}/stock-movements`` -- same
coarse/fine split as ``RecordStockMovementUseCase``, gated
``inventory.read``.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import StockMovementListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    stock_movement_to_dto,
)
from restaurant_os_api.modules.operations.domain.exceptions import InventoryItemNotFoundError
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryItemRepository,
    StockMovementRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "inventory.read"


class ListStockMovementsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        inventory_item_repository_factory: Callable[[AsyncSession], InventoryItemRepository],
        stock_movement_repository_factory: Callable[[AsyncSession], StockMovementRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._inventory_item_repository_factory = inventory_item_repository_factory
        self._stock_movement_repository_factory = stock_movement_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self,
        tenant_id: str,
        user_id: str,
        inventory_item_id: str,
        *,
        offset: int,
        limit: int,
    ) -> StockMovementListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            item_repo = self._inventory_item_repository_factory(uow.session)
            movement_repo = self._stock_movement_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            item = await item_repo.get_by_id(tenant_id, inventory_item_id)
            if item is None:
                raise InventoryItemNotFoundError(inventory_item_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=item.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            movements, total = await movement_repo.list_for_item(
                tenant_id, inventory_item_id, offset=offset, limit=limit
            )
            dtos = [stock_movement_to_dto(m) for m in movements]
        return StockMovementListResultDTO(movements=dtos, total=total, offset=offset, limit=limit)
