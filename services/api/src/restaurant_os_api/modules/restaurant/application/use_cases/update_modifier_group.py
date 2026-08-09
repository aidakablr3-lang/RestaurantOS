"""UpdateModifierGroupUseCase.

Restaurant Platform Architecture SS7's ``PATCH /api/v1/modifier-groups/
{id}``. No name-conflict check -- Architecture SS3.1 explicitly
declines to enforce uniqueness on ``ModifierGroup.name``.

No domain event is published -- Architecture SS11's event catalogue
names only ``ModifierGroupCreated``, no ``Updated`` counterpart,
matching ``TableZone``/``MenuCategory``'s own precedent.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import (
    ModifierGroupDTO,
    UpdateModifierGroupRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._modifier_group_mapper import (
    modifier_group_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import ModifierSelectionType
from restaurant_os_api.modules.restaurant.domain.exceptions import ModifierGroupNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import ModifierGroupRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateModifierGroupUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        modifier_group_repository_factory: Callable[[AsyncSession], ModifierGroupRepository],
    ) -> None:
        self._session_factory = session_factory
        self._modifier_group_repository_factory = modifier_group_repository_factory

    async def execute(
        self, tenant_id: str, request: UpdateModifierGroupRequestDTO
    ) -> ModifierGroupDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            modifier_group_repo = self._modifier_group_repository_factory(uow.session)

            modifier_group = await modifier_group_repo.get_by_id(
                tenant_id, request.modifier_group_id
            )
            if modifier_group is None:
                raise ModifierGroupNotFoundError(request.modifier_group_id)

            modifier_group.name = request.name
            modifier_group.selection_type = ModifierSelectionType(request.selection_type)

            modifier_group = await modifier_group_repo.update(modifier_group)

        return modifier_group_to_dto(modifier_group)
