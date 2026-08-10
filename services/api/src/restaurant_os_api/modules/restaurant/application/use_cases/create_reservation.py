"""CreateReservationUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/branches/
{branch_id}/reservations`` -- foundation CRUD only, no waitlist logic
(SS7's own words). ``branch_id`` is loaded scoped to the caller's own
tenant first, mirroring ``CreateTableUseCase``'s own check. If
``table_id`` is supplied, it is loaded and verified to belong to that
same branch -- a table that exists but belongs to a different branch
(or tenant, or doesn't exist) is ``TableNotFoundError``, the same
cross-scope-is-404 discipline every other Create use case in this
module already follows. ``table_id`` is optional (Architecture SS3.1:
"a request can exist before a specific table is assigned").

A new reservation always starts ``ReservationStatus.REQUESTED`` (the
domain entity's own only construction-time status -- every other
status is reached exclusively through its transition methods, never
assigned directly). ``customer_id`` is always ``None`` on create --
see ``reservation_dto.py``'s own docstring for why. ``sync_version``
starts at ``0``, matching every other "Exclusive shared state"
entity's own Step 4.0 Decision Lock (no optimistic-concurrency code
is written this sprint).

Publishes ``ReservationCreated`` (Architecture SS11 names this event
explicitly).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateReservationRequestDTO,
    ReservationDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._reservation_mapper import (
    reservation_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import Reservation, ReservationStatus
from restaurant_os_api.modules.restaurant.domain.events import ReservationCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    TableNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    ReservationRepository,
    TableRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateReservationUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        reservation_repository_factory: Callable[[AsyncSession], ReservationRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._table_repository_factory = table_repository_factory
        self._reservation_repository_factory = reservation_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: CreateReservationRequestDTO) -> ReservationDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)
            reservation_repo = self._reservation_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            if request.table_id is not None:
                table = await table_repo.get_by_id(tenant_id, request.table_id)
                if table is None or table.branch_id != request.branch_id:
                    raise TableNotFoundError(request.table_id)

            reservation = await reservation_repo.create(
                Reservation(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    table_id=request.table_id,
                    customer_id=None,
                    party_size=request.party_size,
                    requested_at=request.requested_at,
                    status=ReservationStatus.REQUESTED,
                    sync_version=0,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                ReservationCreated(
                    reservation_id=reservation.id,
                    branch_id=reservation.branch_id,
                    party_size=reservation.party_size,
                    occurred_at=now,
                ),
            )

        return reservation_to_dto(reservation)
