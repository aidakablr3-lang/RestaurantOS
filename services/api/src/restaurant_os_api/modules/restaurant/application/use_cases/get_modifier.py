"""GetModifierUseCase.

Restaurant Platform Architecture SS7's ``GET /api/v1/modifier-groups/
{modifier_group_id}/modifiers/{id}``. Same cross-scope discipline as
``GetMenuItemUseCase`` -- a modifier that exists but belongs to a
*different* group than the URL's own is ``ModifierNotFoundError``, not
a distinguishable error.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import ModifierDTO
from restaurant_os_api.modules.restaurant.application.use_cases._modifier_mapper import (
    modifier_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import ModifierNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import ModifierRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetModifierUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        modifier_repository_factory: Callable[[AsyncSession], ModifierRepository],
    ) -> None:
        self._session_factory = session_factory
        self._modifier_repository_factory = modifier_repository_factory

    async def execute(
        self, tenant_id: str, modifier_group_id: str, modifier_id: str
    ) -> ModifierDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            modifier_repo = self._modifier_repository_factory(uow.session)
            modifier = await modifier_repo.get_by_id(tenant_id, modifier_id)

        if modifier is None or modifier.modifier_group_id != modifier_group_id:
            raise ModifierNotFoundError(modifier_id)

        return modifier_to_dto(modifier)
