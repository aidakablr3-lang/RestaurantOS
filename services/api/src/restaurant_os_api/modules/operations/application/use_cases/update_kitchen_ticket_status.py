"""UpdateKitchenTicketStatusUseCase.

Flat ``POST /api/v1/kitchen-tickets/{id}/status`` -- ``KitchenTicket``
carries no ``branch_id`` column, so the branch is resolved by chaining
``ticket.order_id -> Order.branch_id``, then the same coarse/fine
authorization split as ``ChangeTableStatusUseCase``. Publishes
``TicketReady`` only when the target status is ``ready`` (the one
transition Architecture doc SS11 names a consumer for).

Cascades the ticket-level transition down two layers:

- Every ``KitchenItem`` still behind it (full-day operational
  simulation finding: bumping a ticket to ``in_progress``/``ready``
  left its own items showing ``queued`` on the KDS, since nothing here
  ever touched them). An item already at or past the target is left
  alone -- only items still behind get pushed forward, one domain-legal
  step at a time (``KitchenItem`` has no ``queued -> ready``
  transition, so a ticket jumping straight to ``ready`` still routes a
  still-``queued`` item through ``start()`` first). ``KitchenItemStatus``
  stops at ``ready`` by design (see its own entity docstring), so
  ``served`` has no ``KitchenItem``-level cascade.
- The ``OrderItem`` each ``KitchenItem`` points back at, via
  ``order_item_id`` -- ``ready`` pushes a still-``fired`` ``OrderItem``
  to ``ready``; ``served`` pushes a ``ready`` one to ``served`` and, in
  the same step, deducts that item's recipe ingredients from inventory
  (see ``_recipe_deduction.py``'s own docstring for the full mechanics
  and disclosed limitations). Once *every* non-``voided`` item on the
  order has itself reached ``served``, the ``Order`` itself is
  transitioned to ``served`` and ``OrderServed`` is published --
  "kitchen finishes -> order marked served" (see ``Order``'s own entity
  docstring) is this cascade's own terminal step, not a separate
  trigger.
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
from restaurant_os_api.modules.operations.application.use_cases._recipe_deduction import (
    deduct_recipe_inventory_for_served_item,
)
from restaurant_os_api.modules.operations.domain.entities import (
    KitchenItemStatus,
    KitchenTicketStatus,
    OrderItemLineStatus,
    OrderStatus,
)
from restaurant_os_api.modules.operations.domain.events import OrderServed, TicketReady
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidKitchenTicketStatusTransitionError,
    KitchenTicketNotFoundError,
    OrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryItemRepository,
    KitchenTicketRepository,
    OrderRepository,
    RecipeRepository,
    StockMovementRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, MenuItemRepository
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
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        recipe_repository_factory: Callable[[AsyncSession], RecipeRepository],
        inventory_item_repository_factory: Callable[[AsyncSession], InventoryItemRepository],
        stock_movement_repository_factory: Callable[[AsyncSession], StockMovementRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._kitchen_ticket_repository_factory = kitchen_ticket_repository_factory
        self._order_repository_factory = order_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._recipe_repository_factory = recipe_repository_factory
        self._inventory_item_repository_factory = inventory_item_repository_factory
        self._stock_movement_repository_factory = stock_movement_repository_factory
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
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            recipe_repo = self._recipe_repository_factory(uow.session)
            inventory_item_repo = self._inventory_item_repository_factory(uow.session)
            stock_movement_repo = self._stock_movement_repository_factory(uow.session)
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
            if target in (KitchenTicketStatus.IN_PROGRESS, KitchenTicketStatus.READY):
                for item in items:
                    changed = False
                    if item.status == KitchenItemStatus.QUEUED:
                        item.start()
                        changed = True
                    if (
                        target == KitchenTicketStatus.READY
                        and item.status == KitchenItemStatus.IN_PROGRESS
                    ):
                        item.mark_ready()
                        changed = True
                    if changed:
                        await kitchen_ticket_repo.update_item(item)

            if target in (KitchenTicketStatus.READY, KitchenTicketStatus.SERVED):
                for item in items:
                    order_item = await order_repo.get_item_by_id(tenant_id, item.order_item_id)
                    if order_item is None:
                        continue
                    if (
                        target == KitchenTicketStatus.READY
                        and order_item.line_status == OrderItemLineStatus.FIRED
                    ):
                        order_item.ready()
                        await order_repo.update_item(order_item)
                    elif (
                        target == KitchenTicketStatus.SERVED
                        and order_item.line_status == OrderItemLineStatus.READY
                    ):
                        order_item.serve()
                        await order_repo.update_item(order_item)
                        await deduct_recipe_inventory_for_served_item(
                            tenant_id=tenant_id,
                            order_item=order_item,
                            now=now,
                            menu_item_repo=menu_item_repo,
                            recipe_repo=recipe_repo,
                            inventory_item_repo=inventory_item_repo,
                            stock_movement_repo=stock_movement_repo,
                            branch_repo=branch_repo,
                            outbox=outbox,
                        )

                if target == KitchenTicketStatus.SERVED and order.status == OrderStatus.FIRED:
                    order_items = await order_repo.get_items(tenant_id, order.id)
                    non_voided = [
                        i for i in order_items if i.line_status != OrderItemLineStatus.VOIDED
                    ]
                    if non_voided and all(
                        i.line_status == OrderItemLineStatus.SERVED for i in non_voided
                    ):
                        order.mark_served()
                        await order_repo.update(order)
                        await outbox.publish(
                            tenant_id, OrderServed(order_id=order.id, occurred_at=now)
                        )

        return kitchen_ticket_to_dto(ticket, items)
