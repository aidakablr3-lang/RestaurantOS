"""CreateModifierUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/modifier-groups/
{modifier_group_id}/modifiers``. ``modifier_group_id`` is loaded scoped
to the caller's own tenant first -- a modifier group that exists but
belongs to another tenant is treated identically to one that does not
exist at all (``ModifierGroupNotFoundError``, never a distinguishable
403), the same "belt and suspenders" pattern ``CreateMenuItemUseCase``
already established for its own parent-scope check against
``menu_category_id``.

Publishes ``ModifierCreated`` (SS11 names this event explicitly).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateModifierRequestDTO,
    ModifierDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._modifier_mapper import (
    modifier_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import Modifier
from restaurant_os_api.modules.restaurant.domain.events import ModifierCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import ModifierGroupNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    ModifierGroupRepository,
    ModifierRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateModifierUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        modifier_group_repository_factory: Callable[[AsyncSession], ModifierGroupRepository],
        modifier_repository_factory: Callable[[AsyncSession], ModifierRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._modifier_group_repository_factory = modifier_group_repository_factory
        self._modifier_repository_factory = modifier_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: CreateModifierRequestDTO) -> ModifierDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            modifier_group_repo = self._modifier_group_repository_factory(uow.session)
            modifier_repo = self._modifier_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            modifier_group = await modifier_group_repo.get_by_id(
                tenant_id, request.modifier_group_id
            )
            if modifier_group is None:
                raise ModifierGroupNotFoundError(request.modifier_group_id)

            modifier = await modifier_repo.create(
                Modifier(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    modifier_group_id=request.modifier_group_id,
                    name=request.name,
                    price_delta=request.price_delta,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                ModifierCreated(
                    modifier_id=modifier.id,
                    modifier_group_id=modifier.modifier_group_id,
                    name=modifier.name,
                    occurred_at=now,
                ),
            )

        return modifier_to_dto(modifier)
