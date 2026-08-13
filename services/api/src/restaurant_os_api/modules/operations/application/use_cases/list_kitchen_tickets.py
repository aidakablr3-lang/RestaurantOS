"""ListKitchenTicketsUseCase.

``GET /api/v1/branches/{branch_id}/kitchen-tickets`` -- the live KDS
feed (Architecture doc SS6).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import KitchenTicketListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._kitchen_mapper import (
    kitchen_ticket_to_dto,
)
from restaurant_os_api.modules.operations.domain.ports import KitchenTicketRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListKitchenTicketsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        kitchen_ticket_repository_factory: Callable[[AsyncSession], KitchenTicketRepository],
    ) -> None:
        self._session_factory = session_factory
        self._kitchen_ticket_repository_factory = kitchen_ticket_repository_factory

    async def execute(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> KitchenTicketListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            kitchen_ticket_repo = self._kitchen_ticket_repository_factory(uow.session)
            tickets, total = await kitchen_ticket_repo.list_for_branch(
                tenant_id, branch_id, offset=offset, limit=limit
            )
            dtos = []
            for ticket in tickets:
                items = await kitchen_ticket_repo.get_items(tenant_id, ticket.id)
                dtos.append(kitchen_ticket_to_dto(ticket, items))
        return KitchenTicketListResultDTO(tickets=dtos, total=total, offset=offset, limit=limit)
