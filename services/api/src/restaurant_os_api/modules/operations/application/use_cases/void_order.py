"""VoidOrderUseCase.

Architecture doc SS6's flat ``POST /api/v1/orders/{id}/void``, same
coarse/fine-grained split as ``FireOrderUseCase``/``CloseOrderUseCase``.
Delegates the precondition to ``Order.void()`` (``open``/``fired ->
voided``).

**Disclosed gap against the architecture doc's own SS6 sketch:** that
sketch additionally called for a post-fire void to require "manager
scope," not just ``order.manage``. This codebase's RBAC has no existing
primitive for a scope *tier* distinct from branch-vs-tenant-wide scope
(``ResolvedPermissions`` answers "does this grant cover this branch,"
not "is this grant a manager-level one") -- building one would be new
RBAC architecture, real scope beyond this single use case. Not
implemented here; every caller with ``order.manage`` at the order's
branch can void at any voidable stage, pre- or post-fire. Flagged as a
known limitation, not silently dropped.

Does not cascade-void the order's own items -- a voided order's
``OrderItem`` rows are simply left in whatever line status they were
already in (this mirrors the architecture doc's own "correction, not
retroactive rewrite" stance elsewhere, e.g. ``Order.closed_at``). It
*does* cascade-cancel any already-created ``KitchenTicket`` for this
order (operational-gap fix, 2026-09-08 -- see
``_kitchen_ticket_cancellation.py``): a post-fire void now tells the
kitchen to stop, rather than leaving a ticket sitting on the KDS with
nothing signalling the order is dead. Publishes ``OrderVoided`` plus
one ``KitchenTicketCancelled`` per ticket the cascade actually cancels.

**Still-disclosed limitation, not fixed here (out of scope per this
change's own instructions):** if some of the order's items already
reached ``served`` before the void (a partially-served, still-``fired``
order -- the order itself only reaches ``served`` once *every*
non-voided item has), their recipe-ingredient inventory deduction
(``_recipe_deduction.py``, run at serve time) is not reversed by this
cascade. Noted in the architecture doc (SS3.2) rather than fixed --
inventory isn't in real use yet, so this has no live impact today.

Reverts a ``table_id`` order's ``Table`` back to ``available``, same
guard and reasoning as ``CloseOrderUseCase``'s own identical cascade --
voiding legitimately ends the table's association with this order too,
but only claims the transition if the table is still ``occupied``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import OrderDTO
from restaurant_os_api.modules.operations.application.use_cases._kitchen_ticket_cancellation import (
    cancel_kitchen_tickets_for_order,
)
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.application.use_cases._table_release import (
    release_table_if_occupied,
)
from restaurant_os_api.modules.operations.domain.events import OrderVoided
from restaurant_os_api.modules.operations.domain.exceptions import OrderNotFoundError
from restaurant_os_api.modules.operations.domain.ports import (
    KitchenTicketRepository,
    OrderRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository, TableRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "order.manage"


class VoidOrderUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        kitchen_ticket_repository_factory: Callable[[AsyncSession], KitchenTicketRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._table_repository_factory = table_repository_factory
        self._kitchen_ticket_repository_factory = kitchen_ticket_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, user_id: str, order_id: str) -> OrderDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)
            kitchen_ticket_repo = self._kitchen_ticket_repository_factory(uow.session)
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

            order.void()
            order = await order_repo.update(order)

            if order.table_id is not None:
                await release_table_if_occupied(table_repo, order_repo, tenant_id, order.table_id)

            await cancel_kitchen_tickets_for_order(
                tenant_id=tenant_id,
                order_id=order.id,
                now=now,
                kitchen_ticket_repo=kitchen_ticket_repo,
                outbox=outbox,
            )

            await outbox.publish(tenant_id, OrderVoided(order_id=order.id, occurred_at=now))

            items = await order_repo.get_items(tenant_id, order.id)

        return order_to_dto(order, items)
