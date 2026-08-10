"""FireOrderUseCase.

Architecture doc SS6's flat ``POST /api/v1/orders/{id}/fire`` -- no
``branch_id`` in the URL, so the router gates coarsely
(``order.manage`` at any scope) and this use case resolves the order's
real branch via ``resolve_and_authorize_branch``, the same split
``ChangeTableStatusUseCase`` established.

Transitions the order ``OPEN -> FIRED`` (raises
``InvalidOrderStatusTransitionError`` if not currently ``OPEN``), fires
every still-``ADDED`` line item, and creates **exactly one**
``KitchenTicket`` covering every fired item.

**Disclosed simplification, not an oversight:** Architecture doc SS3.2
models ``station`` as a per-ticket attribute, implying an order could
in principle fan out into multiple tickets (one per station -- grill,
cold, expo). Doing that for real requires knowing which station each
``MenuItem`` belongs to, and no such column exists on ``menu_items``
today (the Restaurant Platform schema is frozen; adding one is exactly
the kind of change that needs its own migration and its own decision,
not something to slip into this step). So v1 fires **one ticket per
order**, ``station="kitchen"`` -- correct today, and the schema (one
``KitchenTicket`` row per station, ``KitchenItem`` rows linking back to
individual ``OrderItem``s) already supports real per-station splitting
the moment a station column exists, without a redesign.

Publishes ``OrderFired``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import OrderDTO
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.domain.entities import (
    KitchenItem,
    KitchenItemStatus,
    KitchenTicket,
    KitchenTicketStatus,
    OrderItemLineStatus,
)
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
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "order.manage"
_DEFAULT_STATION = "kitchen"


class FireOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        kitchen_ticket_repository_factory: Callable[[AsyncSession], KitchenTicketRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory
        self._kitchen_ticket_repository_factory = kitchen_ticket_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, user_id: str, order_id: str) -> OrderDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            kitchen_ticket_repo = self._kitchen_ticket_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
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

            ticket = await kitchen_ticket_repo.create(
                KitchenTicket(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    order_id=order.id,
                    station=_DEFAULT_STATION,
                    status=KitchenTicketStatus.FIRED,
                    created_at=now,
                )
            )
            for item in fireable_items:
                await kitchen_ticket_repo.add_item(
                    KitchenItem(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        kitchen_ticket_id=ticket.id,
                        order_item_id=item.id,
                        status=KitchenItemStatus.QUEUED,
                        created_at=now,
                    )
                )

            await outbox.publish(tenant_id, OrderFired(order_id=order.id, occurred_at=now))

            all_items = await order_repo.get_items(tenant_id, order.id)

        return order_to_dto(order, all_items)
