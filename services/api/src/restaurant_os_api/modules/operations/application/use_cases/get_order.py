"""GetOrderUseCase."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import OrderDTO
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.domain.exceptions import OrderNotFoundError
from restaurant_os_api.modules.operations.domain.ports import OrderRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory

    async def execute(self, tenant_id: str, branch_id: str, order_id: str) -> OrderDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            order = await order_repo.get_by_id(tenant_id, order_id)
            if order is None or order.branch_id != branch_id:
                raise OrderNotFoundError(order_id)
            items = await order_repo.get_items(tenant_id, order_id)
        return order_to_dto(order, items)
