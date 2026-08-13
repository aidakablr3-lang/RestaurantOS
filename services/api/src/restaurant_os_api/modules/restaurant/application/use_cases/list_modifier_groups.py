"""ListModifierGroupsUseCase -- tenant-scoped, offset/limit paginated,
ordered newest-first (``ModifierGroupRepository.list_for_tenant``'s own
pre-existing ``ORDER BY created_at DESC``, matching
``ListRestaurantsUseCase``'s precedent -- unlike ``MenuCategory``/
``TableZone``, ``ModifierGroup`` has no ``display_order`` column, so
there is no reorder-by-drag-and-drop screen action to preserve).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import ModifierGroupListResultDTO
from restaurant_os_api.modules.restaurant.application.use_cases._modifier_group_mapper import (
    modifier_group_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.ports import ModifierGroupRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListModifierGroupsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        modifier_group_repository_factory: Callable[[AsyncSession], ModifierGroupRepository],
    ) -> None:
        self._session_factory = session_factory
        self._modifier_group_repository_factory = modifier_group_repository_factory

    async def execute(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> ModifierGroupListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            modifier_group_repo = self._modifier_group_repository_factory(uow.session)
            modifier_groups, total = await modifier_group_repo.list_for_tenant(
                tenant_id, offset=offset, limit=limit
            )

        return ModifierGroupListResultDTO(
            modifier_groups=[modifier_group_to_dto(g) for g in modifier_groups],
            total=total,
            offset=offset,
            limit=limit,
        )
