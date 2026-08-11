"""ListDiscountsUseCase. ``GET /api/v1/discounts``."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import DiscountListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._discount_mapper import (
    discount_to_dto,
)
from restaurant_os_api.modules.operations.domain.ports import DiscountRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListDiscountsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        discount_repository_factory: Callable[[AsyncSession], DiscountRepository],
    ) -> None:
        self._session_factory = session_factory
        self._discount_repository_factory = discount_repository_factory

    async def execute(self, tenant_id: str, *, offset: int, limit: int) -> DiscountListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            discount_repo = self._discount_repository_factory(uow.session)
            discounts, total = await discount_repo.list_for_tenant(
                tenant_id, offset=offset, limit=limit
            )
            dtos = [discount_to_dto(d) for d in discounts]
        return DiscountListResultDTO(discounts=dtos, total=total, offset=offset, limit=limit)
