"""CreateOrderUseCase.

Architecture doc SS6's ``POST /api/v1/branches/{branch_id}/orders``.
``branch_id`` is loaded scoped to the caller's own tenant first,
mirroring every Create use case in the restaurant module. If
``table_id``/``tab_id`` is supplied, each is loaded and verified to
belong to that same branch -- a resource that exists but belongs to a
different branch (or tenant, or doesn't exist) is the same
cross-scope-is-404 discipline every restaurant-module Create use case
already follows.

``currency_code`` is resolved server-side from the branch's own
restaurant (``Restaurant.default_currency_code``), never
client-supplied -- there is exactly one correct currency for a given
branch's orders, matching how ``MenuItem.currency_code`` is itself
sourced from the same field.

A new order always starts ``OrderStatus.OPEN`` with ``subtotal_amount``/
``tax_amount`` at ``0`` -- both accumulate as items are added
(``AddOrderItemUseCase``) and, eventually, as tax lines are computed
(a Step 4 Billing concern). Publishes ``OrderPlaced``.

A ``table_id`` order also marks that ``Table`` ``occupied`` (full-day
operational simulation finding: the table board never reflected a
dine-in order actually being open at it). Unconditional, not gated on
the table's current status -- ``ChangeTableStatusUseCase``'s own
docstring already establishes ``Table.status`` has no enforced
transition graph, and a guest being seated legitimately moves a table
out of ``reserved`` the same way it would out of ``available``.
``CloseOrderUseCase``/``VoidOrderUseCase`` are this cascade's other
half, reverting the table once the order's own lifecycle ends.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import CreateOrderRequestDTO, OrderDTO
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.domain.entities import Order, OrderSource, OrderStatus
from restaurant_os_api.modules.operations.domain.events import OrderPlaced
from restaurant_os_api.modules.operations.domain.exceptions import TabNotFoundError
from restaurant_os_api.modules.operations.domain.ports import OrderRepository, TabRepository
from restaurant_os_api.modules.restaurant.domain.entities import TableStatus
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    RestaurantNotFoundError,
    TableNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    RestaurantRepository,
    TableRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        tab_repository_factory: Callable[[AsyncSession], TabRepository],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._restaurant_repository_factory = restaurant_repository_factory
        self._table_repository_factory = table_repository_factory
        self._tab_repository_factory = tab_repository_factory
        self._order_repository_factory = order_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: CreateOrderRequestDTO) -> OrderDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)
            tab_repo = self._tab_repository_factory(uow.session)
            order_repo = self._order_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            restaurant = await restaurant_repo.get_by_id(tenant_id, branch.restaurant_id)
            if restaurant is None:
                raise RestaurantNotFoundError(branch.restaurant_id)

            if request.table_id is not None:
                table = await table_repo.get_by_id(tenant_id, request.table_id)
                if table is None or table.branch_id != request.branch_id:
                    raise TableNotFoundError(request.table_id)
                table.status = TableStatus.OCCUPIED
                await table_repo.update(table)

            if request.tab_id is not None:
                tab = await tab_repo.get_by_id(tenant_id, request.tab_id)
                if tab is None or tab.branch_id != request.branch_id:
                    raise TabNotFoundError(request.tab_id)

            order = await order_repo.create(
                Order(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    order_source=OrderSource(request.order_source),
                    status=OrderStatus.OPEN,
                    subtotal_amount=Decimal(0),
                    tax_amount=Decimal(0),
                    currency_code=restaurant.default_currency_code,
                    opened_at=now,
                    created_at=now,
                    table_id=request.table_id,
                    tab_id=request.tab_id,
                    origin_device_id=request.origin_device_id,
                )
            )

            await outbox.publish(
                tenant_id,
                OrderPlaced(
                    order_id=order.id,
                    branch_id=order.branch_id,
                    order_source=order.order_source.value,
                    occurred_at=now,
                ),
            )

        return order_to_dto(order, [])
