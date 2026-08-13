"""GuestSubmitOrderUseCase.

Backs ``POST /api/v1/qr/{token}/orders/{order_id}/submit`` (guest
ordering) -- the guest-facing equivalent of ``FireOrderUseCase``. Same
rules: transitions ``OPEN -> FIRED`` (idempotent against an
already-``FIRED`` order, same as staff re-fire when a guest adds another
round after the first goes to the kitchen), fires every still-``ADDED``
line, and fans them out across one ``KitchenTicket`` per distinct
station via the shared ``fan_out_items_into_station_tickets`` helper.

No approval gate -- a real disclosed design decision for this feature
(guest orders go straight to the kitchen, no staff review step), not an
oversight. Authorization is ``ensure_guest_order_access`` re-checking the
loaded order's ``branch_id``/``table_id`` against the router's freshly
re-resolved QR token, in place of RBAC.

Publishes ``OrderFired``, same event the staff path publishes -- nothing
downstream (KDS, kitchen tickets) needs to know an order's origin to
process it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import OrderDTO
from restaurant_os_api.modules.operations.application.use_cases._guest_order_guard import (
    ensure_guest_order_access,
)
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.application.use_cases._station_routing import (
    fan_out_items_into_station_tickets,
)
from restaurant_os_api.modules.operations.domain.entities import OrderItemLineStatus
from restaurant_os_api.modules.operations.domain.events import OrderFired
from restaurant_os_api.modules.operations.domain.exceptions import (
    OrderHasNoItemsError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    KitchenTicketRepository,
    OrderRepository,
)
from restaurant_os_api.modules.restaurant.domain.ports import MenuItemRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class GuestSubmitOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        kitchen_ticket_repository_factory: Callable[[AsyncSession], KitchenTicketRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory
        self._kitchen_ticket_repository_factory = kitchen_ticket_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, branch_id: str, table_id: str, order_id: str
    ) -> OrderDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            kitchen_ticket_repo = self._kitchen_ticket_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            order = await order_repo.get_by_id(tenant_id, order_id)
            if order is None:
                raise OrderNotFoundError(order_id)
            ensure_guest_order_access(order, branch_id=branch_id, table_id=table_id)

            items = await order_repo.get_items(tenant_id, order_id)
            fireable_items = [
                item for item in items if item.line_status == OrderItemLineStatus.ADDED
            ]
            if not fireable_items:
                raise OrderHasNoItemsError(order_id)

            order.fire()
            order = await order_repo.update(order)

            for item in fireable_items:
                item.fire()
                await order_repo.update_item(item)

            await fan_out_items_into_station_tickets(
                tenant_id=tenant_id,
                order_id=order.id,
                fireable_items=fireable_items,
                now=now,
                menu_item_repo=menu_item_repo,
                kitchen_ticket_repo=kitchen_ticket_repo,
            )

            await outbox.publish(tenant_id, OrderFired(order_id=order.id, occurred_at=now))

            all_items = await order_repo.get_items(tenant_id, order.id)

        return order_to_dto(order, all_items)
