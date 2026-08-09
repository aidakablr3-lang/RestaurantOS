"""CreateModifierGroupUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/modifier-groups``.
Unlike ``CreateMenuCategoryUseCase``/``CreateTableZoneUseCase``,
``ModifierGroup`` has no FK parent to verify -- it belongs directly to
the tenant (Data Architecture v2.0 Group F), so there is no
parent-scope check here at all. No name-uniqueness check either --
Architecture SS3.1's own ``ModifierGroup`` entry is explicit that a
group named "Size" legitimately repeats across unrelated item
families.

Publishes ``ModifierGroupCreated`` (SS11 names this event explicitly).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateModifierGroupRequestDTO,
    ModifierGroupDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._modifier_group_mapper import (
    modifier_group_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    ModifierGroup,
    ModifierSelectionType,
)
from restaurant_os_api.modules.restaurant.domain.events import ModifierGroupCreated
from restaurant_os_api.modules.restaurant.domain.ports import ModifierGroupRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateModifierGroupUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        modifier_group_repository_factory: Callable[[AsyncSession], ModifierGroupRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._modifier_group_repository_factory = modifier_group_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, request: CreateModifierGroupRequestDTO
    ) -> ModifierGroupDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            modifier_group_repo = self._modifier_group_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            modifier_group = await modifier_group_repo.create(
                ModifierGroup(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    name=request.name,
                    selection_type=ModifierSelectionType(request.selection_type),
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                ModifierGroupCreated(
                    modifier_group_id=modifier_group.id, name=modifier_group.name, occurred_at=now
                ),
            )

        return modifier_group_to_dto(modifier_group)
