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

Does not cascade-void the order's own items or notify any already-
created ``KitchenTicket`` -- a post-fire void needs the kitchen told to
stop, which is real workflow this step doesn't build. Publishes
``OrderVoided``.

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
from restaurant_os_api.modules.operations.application.use_cases._order_mapper import order_to_dto
from restaurant_os_api.modules.operations.application.use_cases._table_release import (
    release_table_if_occupied,
)
from restaurant_os_api.modules.operations.domain.events import OrderVoided
from restaurant_os_api.modules.operations.domain.exceptions import OrderNotFoundError
from restaurant_os_api.modules.operations.domain.ports import OrderRepository
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
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._order_repository_factory = order_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._table_repository_factory = table_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, user_id: str, order_id: str) -> OrderDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            order_repo = self._order_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)
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

            await outbox.publish(tenant_id, OrderVoided(order_id=order.id, occurred_at=now))

            items = await order_repo.get_items(tenant_id, order.id)

        return order_to_dto(order, items)
