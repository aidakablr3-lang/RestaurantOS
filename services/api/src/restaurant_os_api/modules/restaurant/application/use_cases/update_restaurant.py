"""UpdateRestaurantUseCase -- full update of the three editable business
fields (matching ``UpdateTenantUseCase``'s own precedent: ``status`` is
never edited through a generic update, only through the dedicated
``DiscontinueRestaurantUseCase``, so every status transition still goes
through ``Restaurant.discontinue()``'s own guard, never bypassed).
``id``/``tenant_id`` are immutable -- neither appears as a settable
field on ``UpdateRestaurantRequestDTO``, and ``get_by_id`` re-loads the
existing row scoped to the caller's own tenant before any field is
touched, so there is nothing to preserve that could ever drift.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import (
    RestaurantDTO,
    UpdateRestaurantRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._restaurant_mapper import (
    restaurant_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.events import RestaurantUpdated
from restaurant_os_api.modules.restaurant.domain.exceptions import RestaurantNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import RestaurantRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateRestaurantUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._restaurant_repository_factory = restaurant_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: UpdateRestaurantRequestDTO) -> RestaurantDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            restaurant = await restaurant_repo.get_by_id(tenant_id, request.restaurant_id)
            if restaurant is None:
                raise RestaurantNotFoundError(request.restaurant_id)

            restaurant.legal_name = request.legal_name
            restaurant.display_name = request.display_name
            restaurant.default_currency_code = request.default_currency_code
            restaurant = await restaurant_repo.update(restaurant)

            await outbox.publish(
                tenant_id,
                RestaurantUpdated(restaurant_id=restaurant.id, occurred_at=now),
            )

        return restaurant_to_dto(restaurant)
