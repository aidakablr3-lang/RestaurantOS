"""UpdateModifierUseCase.

Restaurant Platform Architecture SS7's ``PATCH /api/v1/modifier-groups/
{modifier_group_id}/modifiers/{id}``. ``modifier_group_id`` is scope
only, never a movable field -- the same reasoning
``UpdateMenuItemUseCase`` documents for ``menu_category_id``: neither
entity denormalizes a second, stable parent column the way ``Table``
does with ``branch_id`` alongside its own movable ``table_zone_id``.

No domain event is published -- Architecture SS11's event catalogue
names only ``ModifierCreated``, no ``Updated`` counterpart.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import (
    ModifierDTO,
    UpdateModifierRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._modifier_mapper import (
    modifier_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import ModifierNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import ModifierRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateModifierUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        modifier_repository_factory: Callable[[AsyncSession], ModifierRepository],
    ) -> None:
        self._session_factory = session_factory
        self._modifier_repository_factory = modifier_repository_factory

    async def execute(self, tenant_id: str, request: UpdateModifierRequestDTO) -> ModifierDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            modifier_repo = self._modifier_repository_factory(uow.session)

            modifier = await modifier_repo.get_by_id(tenant_id, request.modifier_id)
            if modifier is None or modifier.modifier_group_id != request.modifier_group_id:
                raise ModifierNotFoundError(request.modifier_id)

            modifier.name = request.name
            modifier.price_delta = request.price_delta

            modifier = await modifier_repo.update(modifier)

        return modifier_to_dto(modifier)
