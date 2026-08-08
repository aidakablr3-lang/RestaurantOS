"""CreateRestaurantUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/restaurants``.
``tenant_id`` always comes from the caller's own verified access token
(the router's ``AuthenticatedPrincipalDTO.tenant_id``), never from the
request body -- there is no ``tenant_id`` field on
``CreateRestaurantRequestDTO`` at all, so there is no client-supplied
value to even consider trusting.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateRestaurantRequestDTO,
    RestaurantDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._restaurant_mapper import (
    restaurant_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import Restaurant, RestaurantStatus
from restaurant_os_api.modules.restaurant.domain.events import RestaurantCreated
from restaurant_os_api.modules.restaurant.domain.ports import RestaurantRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateRestaurantUseCase:
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

    async def execute(self, tenant_id: str, request: CreateRestaurantRequestDTO) -> RestaurantDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            restaurant = await restaurant_repo.create(
                Restaurant(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    legal_name=request.legal_name,
                    display_name=request.display_name,
                    default_currency_code=request.default_currency_code,
                    status=RestaurantStatus.ACTIVE,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                RestaurantCreated(
                    restaurant_id=restaurant.id,
                    tenant_id=tenant_id,
                    legal_name=restaurant.legal_name,
                    display_name=restaurant.display_name,
                    occurred_at=now,
                ),
            )

        return restaurant_to_dto(restaurant)
