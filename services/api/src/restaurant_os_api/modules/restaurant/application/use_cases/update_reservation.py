"""UpdateReservationUseCase.

Restaurant Platform Architecture SS7's ``PATCH /api/v1/branches/
{branch_id}/reservations/{id}`` -- the *only* mutation route
Reservation gets besides create (unlike ``Table``, SS7 gives
Reservation no separate flat status-change endpoint), so this one use
case handles both plain field edits (``table_id`` reassignment,
``party_size``) and status transitions in a single call.

Status transitions are **never** assigned directly -- ``request.status``
is compared against the reservation's current status, and a genuine
change is routed through the matching domain transition method
(``confirm()``/``seat()``/``complete()``/``mark_no_show()``/``cancel()``),
which raises ``InvalidReservationStatusTransitionError`` itself if the
transition isn't legal from the current state (see the ``Reservation``
entity's own ``_transition_to``). A target status equal to the
reservation's *current* status is treated as "no transition
requested" -- this lets a caller PATCH ``table_id``/``party_size``
alone by resubmitting the reservation's own current status, without
forcing every field edit to also be a valid state transition.
``REQUESTED`` is never a valid transition *target* from any other
state (the entity defines no method that re-enters it -- only
``create_reservation.py`` ever produces a ``REQUESTED`` row); a caller
that requests it while not already ``REQUESTED`` gets the same
``InvalidReservationStatusTransitionError`` every other illegal
transition raises, not a silently-ignored no-op.

If ``table_id`` changes to a non-null value, it is re-verified to
belong to the *same* branch as the reservation itself -- identical to
the check ``CreateReservationUseCase``/``UpdateTableUseCase`` already
perform.

Publishes ``ReservationStatusChanged`` only when an actual transition
occurs -- never on a plain field edit.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import (
    ReservationDTO,
    UpdateReservationRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._reservation_mapper import (
    reservation_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import Reservation, ReservationStatus
from restaurant_os_api.modules.restaurant.domain.events import ReservationStatusChanged
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    InvalidReservationStatusTransitionError,
    ReservationNotFoundError,
    TableNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    ReservationRepository,
    TableRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


def _apply_transition(reservation: Reservation, target: ReservationStatus) -> None:
    if target == ReservationStatus.CONFIRMED:
        reservation.confirm()
    elif target == ReservationStatus.SEATED:
        reservation.seat()
    elif target == ReservationStatus.COMPLETED:
        reservation.complete()
    elif target == ReservationStatus.NO_SHOW:
        reservation.mark_no_show()
    elif target == ReservationStatus.CANCELED:
        reservation.cancel()
    else:
        # target == ReservationStatus.REQUESTED -- no domain method
        # re-enters this state from any other one.
        raise InvalidReservationStatusTransitionError(
            reservation.id, reservation.status.value, target.value
        )


class UpdateReservationUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        reservation_repository_factory: Callable[[AsyncSession], ReservationRepository],
        table_repository_factory: Callable[[AsyncSession], TableRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._reservation_repository_factory = reservation_repository_factory
        self._table_repository_factory = table_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: UpdateReservationRequestDTO) -> ReservationDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            reservation_repo = self._reservation_repository_factory(uow.session)
            table_repo = self._table_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            reservation = await reservation_repo.get_by_id(tenant_id, request.reservation_id)
            if reservation is None or reservation.branch_id != request.branch_id:
                raise ReservationNotFoundError(request.reservation_id)

            if request.table_id != reservation.table_id and request.table_id is not None:
                table = await table_repo.get_by_id(tenant_id, request.table_id)
                if table is None or table.branch_id != reservation.branch_id:
                    raise TableNotFoundError(request.table_id)

            reservation.table_id = request.table_id
            if request.party_size is not None:
                reservation.party_size = request.party_size

            target_status = (
                ReservationStatus(request.status) if request.status is not None else reservation.status
            )
            status_changed = target_status != reservation.status
            previous_status = reservation.status
            if status_changed:
                _apply_transition(reservation, target_status)

            reservation = await reservation_repo.update(reservation)

            if status_changed:
                await outbox.publish(
                    tenant_id,
                    ReservationStatusChanged(
                        reservation_id=reservation.id,
                        previous_status=previous_status.value,
                        new_status=reservation.status.value,
                        occurred_at=now,
                    ),
                )

        return reservation_to_dto(reservation)
