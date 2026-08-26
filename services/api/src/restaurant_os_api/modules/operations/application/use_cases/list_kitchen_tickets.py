"""ListKitchenTicketsUseCase.

``GET /api/v1/branches/{branch_id}/kitchen-tickets`` -- the live KDS
feed (Architecture doc SS6).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import KitchenTicketListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._kitchen_mapper import (
    kitchen_item_to_dto,
    kitchen_ticket_to_dto,
    resolve_kitchen_item_identity,
)
from restaurant_os_api.modules.operations.domain.ports import (
    KitchenTicketRepository,
    OrderRepository,
)
from restaurant_os_api.modules.restaurant.domain.ports import MenuItemRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListKitchenTicketsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        kitchen_ticket_repository_factory: Callable[[AsyncSession], KitchenTicketRepository],
        order_repository_factory: Callable[[AsyncSession], OrderRepository],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
    ) -> None:
        self._session_factory = session_factory
        self._kitchen_ticket_repository_factory = kitchen_ticket_repository_factory
        self._order_repository_factory = order_repository_factory
        self._menu_item_repository_factory = menu_item_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> KitchenTicketListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            kitchen_ticket_repo = self._kitchen_ticket_repository_factory(uow.session)
            order_repo = self._order_repository_factory(uow.session)
            menu_item_repo = self._menu_item_repository_factory(uow.session)

            tickets, total = await kitchen_ticket_repo.list_for_branch(
                tenant_id, branch_id, offset=offset, limit=limit
            )
            items_by_ticket = {
                ticket.id: await kitchen_ticket_repo.get_items(tenant_id, ticket.id)
                for ticket in tickets
            }

            # Batch-resolve every kitchen item's menu item name/quantity in
            # two passes (one order-items fetch across every distinct
            # order, one menu-item fetch per distinct menu item) rather
            # than a lookup per kitchen item, which would be an N+1 across
            # the whole board on every ~8s KDS poll.
            order_ids = list({ticket.order_id for ticket in tickets})
            order_items = (
                await order_repo.list_items_for_orders(tenant_id, order_ids) if order_ids else []
            )
            order_items_by_id = {oi.id: oi for oi in order_items}

            menu_item_ids = {oi.menu_item_id for oi in order_items}
            menu_items_by_id = {}
            for menu_item_id in menu_item_ids:
                menu_item = await menu_item_repo.get_by_id(tenant_id, menu_item_id)
                if menu_item is not None:
                    menu_items_by_id[menu_item_id] = menu_item

            dtos = []
            for ticket in tickets:
                item_dtos = []
                for item in items_by_ticket[ticket.id]:
                    name, quantity = resolve_kitchen_item_identity(
                        item, order_items_by_id=order_items_by_id, menu_items_by_id=menu_items_by_id
                    )
                    item_dtos.append(
                        kitchen_item_to_dto(item, menu_item_name=name, quantity=quantity)
                    )
                dtos.append(kitchen_ticket_to_dto(ticket, item_dtos))
        return KitchenTicketListResultDTO(tickets=dtos, total=total, offset=offset, limit=limit)
