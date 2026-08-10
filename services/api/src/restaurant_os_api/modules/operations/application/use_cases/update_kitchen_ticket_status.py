"""UpdateKitchenTicketStatusUseCase.

Flat ``POST /api/v1/kitchen-tickets/{id}/status`` -- ``KitchenTicket``
carries no ``branch_id`` column, so the branch is resolved by chaining
``ticket.order_id -> Order.branch_id``, then the same coarse/fine
authorization split as ``ChangeTableStatusUseCase``. Publishes
``TicketReady`` only when the target status is ``ready`` (the one
transition Architecture doc SS11 names a consumer for).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import (
    ChangeKitchenTicketStatusRequestDTO,
    KitchenTicketDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._kitchen_mapper import (
    kitchen_ticket_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import KitchenTicketStatus
from restaurant_os_api.modules.operations.domain.events import TicketReady
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidKitchenTicketStatusTransitionError,
    KitchenTicketNotFoundError,
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

PERMISSION_CODE = "kitchen.manage"

_TRANSITIONS = {
    KitchenTicketStatus.IN_PROGRESS: "start",
    KitchenTicketStatus.READY: "mark_ready",
    KitchenTicketStatus.SERVED: "mark_served",
}


class UpdateKitchenTicketStatusUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        kitchen_ticket_repository_factory: Callable[[AsyncSession], KitchenTicketRepository],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._kitchen_ticket_repository_factory = kitchen_ticket_repository_factory
        self._order_repository_factory = order_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, user_id: str, request: ChangeKitchenTicketStatusRequestDTO
    ) -> KitchenTicketDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            kitchen_ticket_repo = self._kitchen_ticket_repository_factory(uow.session)
            order_repo = self._order_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            ticket = await kitchen_ticket_repo.get_by_id(tenant_id, request.kitchen_ticket_id)
            if ticket is None:
                raise KitchenTicketNotFoundError(request.kitchen_ticket_id)

            order = await order_repo.get_by_id(tenant_id, ticket.order_id)
            if order is None:
                raise OrderNotFoundError(ticket.order_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=order.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            target = KitchenTicketStatus(request.status)
            method_name = _TRANSITIONS.get(target)
            if method_name is None:
                raise InvalidKitchenTicketStatusTransitionError(
                    ticket.id, ticket.status.value, target.value
                )
            getattr(ticket, method_name)()
            ticket = await kitchen_ticket_repo.update(ticket)

            if target == KitchenTicketStatus.READY:
                await outbox.publish(
                    tenant_id,
                    TicketReady(kitchen_ticket_id=ticket.id, order_id=order.id, occurred_at=now),
                )

            items = await kitchen_ticket_repo.get_items(tenant_id, ticket.id)

        return kitchen_ticket_to_dto(ticket, items)
