"""Unit tests for Reservation CRUD use cases (Sprint 5 Step 4.11) --
in-memory fakes, no network/DB access.

RBAC is deliberately not exercised here: every Reservation route is
nested under ``branch_id`` and gated entirely by the router-level
``require_branch_permission`` dependency, the same shape
``CreateTableUseCase``/``UpdateTableUseCase``/``GetTableUseCase``/
``ListTablesUseCase`` already use -- none of those use cases take a
``user_id``/``resolve_user_permissions`` parameter either, and none of
their own unit test files exercise an RBAC matrix (that lives in the
router's own integration tests, e.g. ``test_table_router.py``). Only
``ChangeTableStatusUseCase``, the one *flat*-route exception, needs
RBAC at the use-case layer -- Reservation has no such exception.
Idempotency is likewise router-only (``IdempotencyGuard``), tested at
the integration layer, matching every other entity's own precedent.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    CreateReservationRequestDTO,
    UpdateReservationRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateReservationUseCase,
    GetReservationUseCase,
    ListReservationsUseCase,
    UpdateReservationUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    Reservation,
    ReservationStatus,
    Table,
    TableStatus,
)
from restaurant_os_api.modules.restaurant.domain.events import (
    ReservationCreated,
    ReservationStatusChanged,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    InvalidReservationStatusTransitionError,
    ReservationNotFoundError,
    TableNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryBranchRepository,
    InMemoryReservationRepository,
    InMemoryTableRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
OTHER_BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
TABLE_ZONE_ID = "01ARZ3NDEKTSV4RRFFQ6TZONE1"
TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABLE1"
OTHER_TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABLE2"
RESERVATION_ID = "01ARZ3NDEKTSV4RRFFQ6RESV01"
REQUESTED_AT = datetime(2026, 6, 1, 19, 0, tzinfo=UTC)


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": datetime.now(UTC),
        "address_id": None,
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _table(**overrides) -> Table:
    defaults = {
        "id": TABLE_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "table_zone_id": TABLE_ZONE_ID,
        "table_number": "12A",
        "capacity": 4,
        "status": TableStatus.AVAILABLE,
        "sync_version": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Table(**defaults)


def _reservation(**overrides) -> Reservation:
    defaults = {
        "id": RESERVATION_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "party_size": 4,
        "requested_at": REQUESTED_AT,
        "status": ReservationStatus.REQUESTED,
        "sync_version": 0,
        "created_at": datetime.now(UTC),
        "table_id": None,
        "customer_id": None,
    }
    defaults.update(overrides)
    return Reservation(**defaults)


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateReservationUseCase:
    def _use_case(
        self, branch_repo, table_repo, reservation_repo, outbox
    ) -> CreateReservationUseCase:
        return CreateReservationUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_repository_factory=lambda _s: table_repo,
            reservation_repository_factory=lambda _s: reservation_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_creates_requested_without_a_table_and_publishes_created(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            branch_repo, InMemoryTableRepository(), InMemoryReservationRepository(), outbox
        )

        result = await use_case.execute(
            TENANT_ID,
            CreateReservationRequestDTO(
                branch_id=BRANCH_ID, party_size=4, requested_at=REQUESTED_AT
            ),
        )

        assert result.status == "requested"
        assert result.table_id is None
        assert result.customer_id is None
        assert result.branch_id == BRANCH_ID
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], ReservationCreated)

    async def test_creates_with_a_valid_table_assigned(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        use_case = self._use_case(
            branch_repo, table_repo, InMemoryReservationRepository(), FakeOutboxWriter()
        )

        result = await use_case.execute(
            TENANT_ID,
            CreateReservationRequestDTO(
                branch_id=BRANCH_ID,
                party_size=2,
                requested_at=REQUESTED_AT,
                table_id=TABLE_ID,
            ),
        )
        assert result.table_id == TABLE_ID

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository(),
            InMemoryTableRepository(),
            InMemoryReservationRepository(),
            FakeOutboxWriter(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateReservationRequestDTO(
                    branch_id=BRANCH_ID, party_size=2, requested_at=REQUESTED_AT
                ),
            )

    async def test_raises_not_found_for_an_unknown_table(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = self._use_case(
            branch_repo,
            InMemoryTableRepository(),
            InMemoryReservationRepository(),
            FakeOutboxWriter(),
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateReservationRequestDTO(
                    branch_id=BRANCH_ID,
                    party_size=2,
                    requested_at=REQUESTED_AT,
                    table_id=TABLE_ID,
                ),
            )

    async def test_raises_not_found_when_the_table_belongs_to_a_different_branch(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_repo = InMemoryTableRepository({TABLE_ID: _table(branch_id=OTHER_BRANCH_ID)})
        use_case = self._use_case(
            branch_repo, table_repo, InMemoryReservationRepository(), FakeOutboxWriter()
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateReservationRequestDTO(
                    branch_id=BRANCH_ID,
                    party_size=2,
                    requested_at=REQUESTED_AT,
                    table_id=TABLE_ID,
                ),
            )

    async def test_raises_not_found_when_the_table_belongs_to_a_different_tenant(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_repo = InMemoryTableRepository({TABLE_ID: _table(tenant_id=OTHER_TENANT_ID)})
        use_case = self._use_case(
            branch_repo, table_repo, InMemoryReservationRepository(), FakeOutboxWriter()
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateReservationRequestDTO(
                    branch_id=BRANCH_ID,
                    party_size=2,
                    requested_at=REQUESTED_AT,
                    table_id=TABLE_ID,
                ),
            )


class TestGetReservationUseCase:
    async def test_returns_the_reservation(self) -> None:
        reservation_repo = InMemoryReservationRepository({RESERVATION_ID: _reservation()})
        use_case = GetReservationUseCase(
            session_factory=_session_factory(),
            reservation_repository_factory=lambda _s: reservation_repo,
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, RESERVATION_ID)
        assert result.id == RESERVATION_ID

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = GetReservationUseCase(
            session_factory=_session_factory(),
            reservation_repository_factory=lambda _s: InMemoryReservationRepository(),
        )

        with pytest.raises(ReservationNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, RESERVATION_ID)

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        reservation_repo = InMemoryReservationRepository(
            {RESERVATION_ID: _reservation(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = GetReservationUseCase(
            session_factory=_session_factory(),
            reservation_repository_factory=lambda _s: reservation_repo,
        )

        with pytest.raises(ReservationNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, RESERVATION_ID)

    async def test_raises_not_found_when_the_reservation_belongs_to_a_different_branch(
        self,
    ) -> None:
        reservation_repo = InMemoryReservationRepository(
            {RESERVATION_ID: _reservation(branch_id=OTHER_BRANCH_ID)}
        )
        use_case = GetReservationUseCase(
            session_factory=_session_factory(),
            reservation_repository_factory=lambda _s: reservation_repo,
        )

        with pytest.raises(ReservationNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, RESERVATION_ID)


class TestListReservationsUseCase:
    async def test_lists_only_the_requested_branchs_reservations_ordered_by_requested_at(
        self,
    ) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        reservation_repo = InMemoryReservationRepository(
            {
                "r1": _reservation(id="r1", requested_at=datetime(2026, 6, 1, 20, 0, tzinfo=UTC)),
                "r2": _reservation(id="r2", requested_at=datetime(2026, 6, 1, 18, 0, tzinfo=UTC)),
                "r3": _reservation(
                    id="r3",
                    requested_at=datetime(2026, 6, 1, 19, 0, tzinfo=UTC),
                    branch_id=OTHER_BRANCH_ID,
                ),
            }
        )
        use_case = ListReservationsUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            reservation_repository_factory=lambda _s: reservation_repo,
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.total == 2
        assert [r.id for r in result.reservations] == ["r2", "r1"]

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = ListReservationsUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            reservation_repository_factory=lambda _s: InMemoryReservationRepository(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

    async def test_pagination_offset_and_limit(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        reservation_repo = InMemoryReservationRepository(
            {
                f"r{i}": _reservation(
                    id=f"r{i}", requested_at=datetime(2026, 6, 1, 12 + i, 0, tzinfo=UTC)
                )
                for i in range(5)
            }
        )
        use_case = ListReservationsUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            reservation_repository_factory=lambda _s: reservation_repo,
        )

        page_1 = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=2)
        page_2 = await use_case.execute(TENANT_ID, BRANCH_ID, offset=2, limit=2)

        assert page_1.total == page_2.total == 5
        assert [r.id for r in page_1.reservations] == ["r0", "r1"]
        assert [r.id for r in page_2.reservations] == ["r2", "r3"]


class TestUpdateReservationUseCase:
    def _use_case(self, reservation_repo, table_repo, outbox) -> UpdateReservationUseCase:
        return UpdateReservationUseCase(
            session_factory=_session_factory(),
            reservation_repository_factory=lambda _s: reservation_repo,
            table_repository_factory=lambda _s: table_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_field_only_edit_resubmitting_current_status_publishes_no_event(self) -> None:
        reservation_repo = InMemoryReservationRepository({RESERVATION_ID: _reservation()})
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        outbox = FakeOutboxWriter()
        use_case = self._use_case(reservation_repo, table_repo, outbox)

        result = await use_case.execute(
            TENANT_ID,
            UpdateReservationRequestDTO(
                reservation_id=RESERVATION_ID,
                branch_id=BRANCH_ID,
                party_size=6,
                status="requested",
                table_id=TABLE_ID,
            ),
        )

        assert result.party_size == 6
        assert result.table_id == TABLE_ID
        assert result.status == "requested"
        assert outbox.published == []

    async def test_a_pure_status_transition_omitting_party_size_leaves_it_unchanged(self) -> None:
        reservation_repo = InMemoryReservationRepository(
            {RESERVATION_ID: _reservation(party_size=4)}
        )
        outbox = FakeOutboxWriter()
        use_case = self._use_case(reservation_repo, InMemoryTableRepository(), outbox)

        result = await use_case.execute(
            TENANT_ID,
            UpdateReservationRequestDTO(
                reservation_id=RESERVATION_ID, branch_id=BRANCH_ID, status="confirmed"
            ),
        )

        assert result.status == "confirmed"
        assert result.party_size == 4
        assert len(outbox.published) == 1

    async def test_a_pure_field_edit_omitting_status_requests_no_transition(self) -> None:
        reservation_repo = InMemoryReservationRepository(
            {RESERVATION_ID: _reservation(party_size=2)}
        )
        outbox = FakeOutboxWriter()
        use_case = self._use_case(reservation_repo, InMemoryTableRepository(), outbox)

        result = await use_case.execute(
            TENANT_ID,
            UpdateReservationRequestDTO(reservation_id=RESERVATION_ID, branch_id=BRANCH_ID, party_size=8),
        )

        assert result.party_size == 8
        assert result.status == "requested"
        assert outbox.published == []

    async def test_unassigning_a_table_by_passing_none_succeeds(self) -> None:
        reservation_repo = InMemoryReservationRepository(
            {RESERVATION_ID: _reservation(table_id=TABLE_ID)}
        )
        use_case = self._use_case(reservation_repo, InMemoryTableRepository(), FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            UpdateReservationRequestDTO(
                reservation_id=RESERVATION_ID,
                branch_id=BRANCH_ID,
                party_size=4,
                status="requested",
                table_id=None,
            ),
        )
        assert result.table_id is None

    async def test_raises_not_found_when_the_new_table_belongs_to_a_different_branch(
        self,
    ) -> None:
        reservation_repo = InMemoryReservationRepository({RESERVATION_ID: _reservation()})
        table_repo = InMemoryTableRepository({TABLE_ID: _table(branch_id=OTHER_BRANCH_ID)})
        use_case = self._use_case(reservation_repo, table_repo, FakeOutboxWriter())

        with pytest.raises(TableNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateReservationRequestDTO(
                    reservation_id=RESERVATION_ID,
                    branch_id=BRANCH_ID,
                    party_size=4,
                    status="requested",
                    table_id=TABLE_ID,
                ),
            )

    async def test_raises_not_found_for_an_unknown_reservation(self) -> None:
        use_case = self._use_case(
            InMemoryReservationRepository(), InMemoryTableRepository(), FakeOutboxWriter()
        )

        with pytest.raises(ReservationNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateReservationRequestDTO(
                    reservation_id=RESERVATION_ID,
                    branch_id=BRANCH_ID,
                    party_size=4,
                    status="requested",
                ),
            )

    async def test_raises_not_found_when_the_reservation_belongs_to_a_different_branch(
        self,
    ) -> None:
        reservation_repo = InMemoryReservationRepository(
            {RESERVATION_ID: _reservation(branch_id=OTHER_BRANCH_ID)}
        )
        use_case = self._use_case(reservation_repo, InMemoryTableRepository(), FakeOutboxWriter())

        with pytest.raises(ReservationNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateReservationRequestDTO(
                    reservation_id=RESERVATION_ID,
                    branch_id=BRANCH_ID,
                    party_size=4,
                    status="requested",
                ),
            )

    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            (ReservationStatus.REQUESTED, "confirmed"),
            (ReservationStatus.CONFIRMED, "seated"),
            (ReservationStatus.SEATED, "completed"),
            (ReservationStatus.REQUESTED, "canceled"),
            (ReservationStatus.CONFIRMED, "canceled"),
            (ReservationStatus.CONFIRMED, "no_show"),
        ],
    )
    async def test_every_valid_transition_succeeds_and_publishes_status_changed(
        self, from_status: ReservationStatus, to_status: str
    ) -> None:
        reservation_repo = InMemoryReservationRepository(
            {RESERVATION_ID: _reservation(status=from_status)}
        )
        outbox = FakeOutboxWriter()
        use_case = self._use_case(reservation_repo, InMemoryTableRepository(), outbox)

        result = await use_case.execute(
            TENANT_ID,
            UpdateReservationRequestDTO(
                reservation_id=RESERVATION_ID,
                branch_id=BRANCH_ID,
                party_size=4,
                status=to_status,
            ),
        )

        assert result.status == to_status
        assert len(outbox.published) == 1
        event = outbox.published[0][1]
        assert isinstance(event, ReservationStatusChanged)
        assert event.previous_status == from_status.value
        assert event.new_status == to_status

    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            (ReservationStatus.REQUESTED, "seated"),
            (ReservationStatus.REQUESTED, "completed"),
            (ReservationStatus.REQUESTED, "no_show"),
            (ReservationStatus.CONFIRMED, "requested"),
            (ReservationStatus.SEATED, "requested"),
            (ReservationStatus.SEATED, "confirmed"),
            (ReservationStatus.SEATED, "canceled"),
            (ReservationStatus.SEATED, "no_show"),
            (ReservationStatus.COMPLETED, "requested"),
            (ReservationStatus.COMPLETED, "confirmed"),
            (ReservationStatus.COMPLETED, "seated"),
            (ReservationStatus.COMPLETED, "canceled"),
            (ReservationStatus.COMPLETED, "no_show"),
            (ReservationStatus.NO_SHOW, "confirmed"),
            (ReservationStatus.NO_SHOW, "seated"),
            (ReservationStatus.NO_SHOW, "completed"),
            (ReservationStatus.NO_SHOW, "canceled"),
            (ReservationStatus.CANCELED, "confirmed"),
            (ReservationStatus.CANCELED, "seated"),
            (ReservationStatus.CANCELED, "completed"),
            (ReservationStatus.CANCELED, "no_show"),
        ],
    )
    async def test_every_invalid_transition_is_rejected(
        self, from_status: ReservationStatus, to_status: str
    ) -> None:
        reservation_repo = InMemoryReservationRepository(
            {RESERVATION_ID: _reservation(status=from_status)}
        )
        outbox = FakeOutboxWriter()
        use_case = self._use_case(reservation_repo, InMemoryTableRepository(), outbox)

        with pytest.raises(InvalidReservationStatusTransitionError):
            await use_case.execute(
                TENANT_ID,
                UpdateReservationRequestDTO(
                    reservation_id=RESERVATION_ID,
                    branch_id=BRANCH_ID,
                    party_size=4,
                    status=to_status,
                ),
            )
        assert outbox.published == []

    async def test_the_three_terminal_statuses_reject_every_outgoing_transition(self) -> None:
        for terminal in (
            ReservationStatus.COMPLETED,
            ReservationStatus.NO_SHOW,
            ReservationStatus.CANCELED,
        ):
            for target in ("requested", "confirmed", "seated", "completed", "no_show", "canceled"):
                if target == terminal.value:
                    continue
                reservation_repo = InMemoryReservationRepository(
                    {RESERVATION_ID: _reservation(status=terminal)}
                )
                use_case = self._use_case(
                    reservation_repo, InMemoryTableRepository(), FakeOutboxWriter()
                )
                with pytest.raises(InvalidReservationStatusTransitionError):
                    await use_case.execute(
                        TENANT_ID,
                        UpdateReservationRequestDTO(
                            reservation_id=RESERVATION_ID,
                            branch_id=BRANCH_ID,
                            party_size=4,
                            status=target,
                        ),
                    )
