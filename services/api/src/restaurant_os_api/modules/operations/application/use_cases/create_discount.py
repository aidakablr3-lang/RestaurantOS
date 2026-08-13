"""CreateDiscountUseCase. ``POST /api/v1/discounts`` -- tenant-wide,
gated ``require_permission("billing.manage")``, the same flat shape
``CreateTaxUseCase`` uses."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import (
    CreateDiscountRequestDTO,
    DiscountDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._discount_mapper import (
    discount_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import Discount, DiscountType
from restaurant_os_api.modules.operations.domain.ports import DiscountRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class CreateDiscountUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        discount_repository_factory: Callable[[AsyncSession], DiscountRepository],
    ) -> None:
        self._session_factory = session_factory
        self._discount_repository_factory = discount_repository_factory

    async def execute(self, tenant_id: str, request: CreateDiscountRequestDTO) -> DiscountDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            discount_repo = self._discount_repository_factory(uow.session)
            discount = await discount_repo.create(
                Discount(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    name=request.name,
                    discount_type=DiscountType(request.discount_type),
                    value=request.value,
                    requires_approval=request.requires_approval,
                    created_at=now,
                    max_value=request.max_value,
                    active_from=request.active_from,
                    active_to=request.active_to,
                )
            )
        return discount_to_dto(discount)
