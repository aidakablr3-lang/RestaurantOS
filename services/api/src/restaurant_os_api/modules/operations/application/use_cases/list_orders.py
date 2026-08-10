"""ListOrdersUseCase."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import OrderListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.domain.ports import OrderRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListOrdersUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> OrderListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            orders, total = await order_repo.list_for_branch(
                tenant_id, branch_id, offset=offset, limit=limit
            )
            # List view omits items -- a per-row N+1 items fetch isn't
            # worth it for a summary list; GetOrderUseCase is the
            # detail path that returns items.
            dtos = [order_to_dto(order, []) for order in orders]
        return OrderListResultDTO(orders=dtos, total=total, offset=offset, limit=limit)
