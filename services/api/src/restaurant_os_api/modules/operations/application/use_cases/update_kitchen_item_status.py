"""UpdateKitchenItemStatusUseCase.

Flat ``POST /api/v1/kitchen-items/{id}/status`` -- resolves the branch
by chaining ``item.kitchen_ticket_id -> KitchenTicket.order_id ->
Order.branch_id``, the same coarse/fine authorization split as
``UpdateKitchenTicketStatusUseCase``. No cross-validation against the
parent ticket's own status is performed (an item can be marked ready
independently of its ticket) -- see ``KitchenTicket``'s own docstring
for why that stricter invariant is disclosed future work, not silently
assumed.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import (
    ChangeKitchenItemStatusRequestDTO,
    KitchenItemDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._kitchen_mapper import (
    kitchen_item_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import KitchenItemStatus
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidKitchenItemStatusTransitionError,
    KitchenItemNotFoundError,
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
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "kitchen.manage"

_TRANSITIONS = {
    KitchenItemStatus.IN_PROGRESS: "start",
    KitchenItemStatus.READY: "mark_ready",
}


class UpdateKitchenItemStatusUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        kitchen_ticket_repository_factory: Callable[[AsyncSession], KitchenTicketRepository],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._kitchen_ticket_repository_factory = kitchen_ticket_repository_factory
        self._order_repository_factory = order_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self, tenant_id: str, user_id: str, request: ChangeKitchenItemStatusRequestDTO
    ) -> KitchenItemDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            kitchen_ticket_repo = self._kitchen_ticket_repository_factory(uow.session)
            order_repo = self._order_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)

            item = await kitchen_ticket_repo.get_item_by_id(tenant_id, request.kitchen_item_id)
            if item is None:
                raise KitchenItemNotFoundError(request.kitchen_item_id)

            ticket = await kitchen_ticket_repo.get_by_id(tenant_id, item.kitchen_ticket_id)
            if ticket is None:
                raise KitchenTicketNotFoundError(item.kitchen_ticket_id)

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

            target = KitchenItemStatus(request.status)
            method_name = _TRANSITIONS.get(target)
            if method_name is None:
                raise InvalidKitchenItemStatusTransitionError(
                    item.id, item.status.value, target.value
                )
            getattr(item, method_name)()
            item = await kitchen_ticket_repo.update_item(item)

        return kitchen_item_to_dto(item)
