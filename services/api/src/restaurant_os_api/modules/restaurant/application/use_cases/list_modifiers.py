"""ListModifiersUseCase -- group-scoped, unpaginated
(``ModifierRepository.list_for_group``'s own pre-existing shape,
mirroring ``ListQRCodesUseCase``'s precedent for an unpaginated child
list). ``modifier_group_id`` is verified to exist (scoped to the
caller's tenant) before listing, mirroring ``ListMenuItemsUseCase``'s
own check.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import ModifierDTO
from restaurant_os_api.modules.restaurant.application.use_cases._modifier_mapper import (
    modifier_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import ModifierGroupNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    ModifierGroupRepository,
    ModifierRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListModifiersUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        modifier_group_repository_factory: Callable[[AsyncSession], ModifierGroupRepository],
        modifier_repository_factory: Callable[[AsyncSession], ModifierRepository],
    ) -> None:
        self._session_factory = session_factory
        self._modifier_group_repository_factory = modifier_group_repository_factory
        self._modifier_repository_factory = modifier_repository_factory

    async def execute(self, tenant_id: str, modifier_group_id: str) -> list[ModifierDTO]:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            modifier_group_repo = self._modifier_group_repository_factory(uow.session)
            modifier_repo = self._modifier_repository_factory(uow.session)

            modifier_group = await modifier_group_repo.get_by_id(tenant_id, modifier_group_id)
            if modifier_group is None:
                raise ModifierGroupNotFoundError(modifier_group_id)

            modifiers = await modifier_repo.list_for_group(tenant_id, modifier_group_id)

        return [modifier_to_dto(m) for m in modifiers]
