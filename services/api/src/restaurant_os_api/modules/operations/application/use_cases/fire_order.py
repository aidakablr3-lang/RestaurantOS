"""FireOrderUseCase.

Architecture doc SS6's flat ``POST /api/v1/orders/{id}/fire`` -- no
``branch_id`` in the URL, so the router gates coarsely
(``order.manage`` at any scope) and this use case resolves the order's
real branch via ``resolve_and_authorize_branch``, the same split
``ChangeTableStatusUseCase`` established.

Transitions the order ``OPEN -> FIRED`` (raises
``InvalidOrderStatusTransitionError`` if the order is in neither
``OPEN`` nor ``FIRED``), fires every still-``ADDED`` line item, and
creates **exactly one** ``KitchenTicket`` covering every item fired by
*this* call.

Callable a second time against an already-``FIRED`` order --
``Order.fire()`` is idempotent for exactly this case (see its own
docstring). ``AddOrderItemUseCase`` lets new lines land on a fired
order in ``ADDED`` status; re-firing filters ``fireable_items`` down to
just those new lines (already-``FIRED``/``VOIDED`` ones are untouched)
and creates a **second** ``KitchenTicket`` for them alone, not a
duplicate of the first. A re-fire with nothing new to send still raises
``OrderHasNoItemsError``, same as firing an empty order the first time.

Fans fireable items out across **one ``KitchenTicket`` per distinct
station** present in this call's own batch -- station-routing (Sprint
7 gap fix): each fireable item's parent ``MenuItem.station`` (migration
0009) decides which ticket it lands on, so a round with both food and
drinks creates a ``kitchen`` ticket and a ``bar`` ticket in the same
``fire()`` call, each independently workable/ready/served from the KDS
side (``KitchenTicket``'s own docstring already modeled "one ticket per
station" -- only the station lookup was missing until now). A batch
where every fireable item shares one station still creates exactly one
ticket, so the common single-station case looks identical to before.

Publishes ``OrderFired``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import OrderDTO
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
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, MenuItemRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "order.manage"


class FireOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        kitchen_ticket_repository_factory: Callable[[AsyncSession], KitchenTicketRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory
        self._kitchen_ticket_repository_factory = kitchen_ticket_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, user_id: str, order_id: str) -> OrderDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            kitchen_ticket_repo = self._kitchen_ticket_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            order = await order_repo.get_by_id(tenant_id, order_id)
            if order is None:
                raise OrderNotFoundError(order_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=order.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

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
