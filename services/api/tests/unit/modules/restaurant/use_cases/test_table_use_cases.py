"""Unit tests for Table CRUD + status-change use cases (Sprint 5 Step
4.5) -- in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.restaurant.application.dto import (
    ChangeTableStatusRequestDTO,
    CreateTableRequestDTO,
    UpdateTableRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    ChangeTableStatusUseCase,
    CreateTableUseCase,
    GetTableUseCase,
    ListTablesUseCase,
    UpdateTableUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    Table,
    TableStatus,
    TableZone,
)
from restaurant_os_api.modules.restaurant.domain.events import (
    TableCreated,
    TableStatusChanged,
    TableUpdated,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    TableNotFoundError,
    TableNumberConflictError,
    TableZoneNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    FakeResolveUserPermissionsUseCase,
    InMemoryBranchRepository,
    InMemoryTableRepository,
    InMemoryTableZoneRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
OTHER_BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
TABLE_ZONE_ID = "01ARZ3NDEKTSV4RRFFQ6TZONE1"
OTHER_TABLE_ZONE_ID = "01ARZ3NDEKTSV4RRFFQ6TZONE2"
TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABLE1"


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


def _table_zone(**overrides) -> TableZone:
    defaults = {
        "id": TABLE_ZONE_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "name": "Patio",
        "display_order": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return TableZone(**defaults)


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


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateTableUseCase:
    def _use_case(self, branch_repo, table_zone_repo, table_repo, outbox) -> CreateTableUseCase:
        return CreateTableUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_zone_repository_factory=lambda _s: table_zone_repo,
            table_repository_factory=lambda _s: table_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_creates_available_and_publishes_table_created(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_zone_repo = InMemoryTableZoneRepository({TABLE_ZONE_ID: _table_zone()})
        table_repo = InMemoryTableRepository()
        outbox = FakeOutboxWriter()
        use_case = self._use_case(branch_repo, table_zone_repo, table_repo, outbox)

        result = await use_case.execute(
            TENANT_ID,
            CreateTableRequestDTO(
                branch_id=BRANCH_ID, table_zone_id=TABLE_ZONE_ID, table_number="12A", capacity=4
            ),
        )

        assert result.table_number == "12A"
        assert result.capacity == 4
        assert result.status == "available"
        assert result.branch_id == BRANCH_ID
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], TableCreated)

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository(),
            InMemoryTableZoneRepository(),
            InMemoryTableRepository(),
            FakeOutboxWriter(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateTableRequestDTO(
                    branch_id=BRANCH_ID, table_zone_id=TABLE_ZONE_ID, table_number="1", capacity=2
                ),
            )

    async def test_raises_not_found_for_an_unknown_table_zone(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = self._use_case(
            branch_repo,
            InMemoryTableZoneRepository(),
            InMemoryTableRepository(),
            FakeOutboxWriter(),
        )

        with pytest.raises(TableZoneNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateTableRequestDTO(
                    branch_id=BRANCH_ID, table_zone_id=TABLE_ZONE_ID, table_number="1", capacity=2
                ),
            )

    async def test_raises_not_found_when_the_table_zone_belongs_to_a_different_branch(
        self,
    ) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_zone_repo = InMemoryTableZoneRepository(
            {TABLE_ZONE_ID: _table_zone(branch_id=OTHER_BRANCH_ID)}
        )
        use_case = self._use_case(
            branch_repo, table_zone_repo, InMemoryTableRepository(), FakeOutboxWriter()
        )

        with pytest.raises(TableZoneNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateTableRequestDTO(
                    branch_id=BRANCH_ID, table_zone_id=TABLE_ZONE_ID, table_number="1", capacity=2
                ),
            )

    async def test_a_duplicate_table_number_under_the_same_branch_is_rejected(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_zone_repo = InMemoryTableZoneRepository({TABLE_ZONE_ID: _table_zone()})
        table_repo = InMemoryTableRepository({TABLE_ID: _table(table_number="12A")})
        use_case = self._use_case(branch_repo, table_zone_repo, table_repo, FakeOutboxWriter())

        with pytest.raises(TableNumberConflictError):
            await use_case.execute(
                TENANT_ID,
                CreateTableRequestDTO(
                    branch_id=BRANCH_ID,
                    table_zone_id=TABLE_ZONE_ID,
                    table_number="12A",
                    capacity=2,
                ),
            )

    async def test_the_same_table_number_under_a_different_branch_is_allowed(self) -> None:
        branch_repo = InMemoryBranchRepository(
            {BRANCH_ID: _branch(), OTHER_BRANCH_ID: _branch(id=OTHER_BRANCH_ID, name="Uptown")}
        )
        table_zone_repo = InMemoryTableZoneRepository(
            {
                TABLE_ZONE_ID: _table_zone(),
                OTHER_TABLE_ZONE_ID: _table_zone(id=OTHER_TABLE_ZONE_ID, branch_id=OTHER_BRANCH_ID),
            }
        )
        table_repo = InMemoryTableRepository({TABLE_ID: _table(table_number="12A")})
        use_case = self._use_case(branch_repo, table_zone_repo, table_repo, FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            CreateTableRequestDTO(
                branch_id=OTHER_BRANCH_ID,
                table_zone_id=OTHER_TABLE_ZONE_ID,
                table_number="12A",
                capacity=2,
            ),
        )
        assert result.branch_id == OTHER_BRANCH_ID


class TestGetTableUseCase:
    async def test_returns_the_table(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        use_case = GetTableUseCase(
            session_factory=_session_factory(), table_repository_factory=lambda _s: table_repo
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)
        assert result.id == TABLE_ID

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = GetTableUseCase(
            session_factory=_session_factory(),
            table_repository_factory=lambda _s: InMemoryTableRepository(),
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(tenant_id=OTHER_TENANT_ID)})
        use_case = GetTableUseCase(
            session_factory=_session_factory(), table_repository_factory=lambda _s: table_repo
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)

    async def test_raises_not_found_when_the_table_belongs_to_a_different_branch(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(branch_id=OTHER_BRANCH_ID)})
        use_case = GetTableUseCase(
            session_factory=_session_factory(), table_repository_factory=lambda _s: table_repo
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ID)


class TestListTablesUseCase:
    async def test_lists_only_the_requested_branchs_tables_ordered_by_table_number(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_repo = InMemoryTableRepository(
            {
                "t1": _table(id="t1", table_number="3"),
                "t2": _table(id="t2", table_number="1"),
                "t3": _table(id="t3", table_number="2"),
                "t4": _table(id="t4", table_number="99", branch_id=OTHER_BRANCH_ID),
            }
        )
        use_case = ListTablesUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_repository_factory=lambda _s: table_repo,
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.total == 3
        assert [t.table_number for t in result.tables] == ["1", "2", "3"]

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = ListTablesUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            table_repository_factory=lambda _s: InMemoryTableRepository(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

    async def test_pagination_offset_and_limit(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_repo = InMemoryTableRepository(
            {f"t{i}": _table(id=f"t{i}", table_number=str(i)) for i in range(5)}
        )
        use_case = ListTablesUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_repository_factory=lambda _s: table_repo,
        )

        page_1 = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=2)
        page_2 = await use_case.execute(TENANT_ID, BRANCH_ID, offset=2, limit=2)

        assert page_1.total == page_2.total == 5
        assert [t.table_number for t in page_1.tables] == ["0", "1"]
        assert [t.table_number for t in page_2.tables] == ["2", "3"]


class TestUpdateTableUseCase:
    def _use_case(self, table_repo, table_zone_repo, outbox) -> UpdateTableUseCase:
        return UpdateTableUseCase(
            session_factory=_session_factory(),
            table_repository_factory=lambda _s: table_repo,
            table_zone_repository_factory=lambda _s: table_zone_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_updates_number_and_capacity_and_publishes_table_updated(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        outbox = FakeOutboxWriter()
        use_case = self._use_case(table_repo, InMemoryTableZoneRepository(), outbox)

        result = await use_case.execute(
            TENANT_ID,
            UpdateTableRequestDTO(
                table_id=TABLE_ID,
                branch_id=BRANCH_ID,
                table_zone_id=TABLE_ZONE_ID,
                table_number="Patio-3",
                capacity=6,
            ),
        )

        assert result.table_number == "Patio-3"
        assert result.capacity == 6
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], TableUpdated)

    async def test_never_touches_status(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.OCCUPIED)})
        use_case = self._use_case(table_repo, InMemoryTableZoneRepository(), FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            UpdateTableRequestDTO(
                table_id=TABLE_ID,
                branch_id=BRANCH_ID,
                table_zone_id=TABLE_ZONE_ID,
                table_number="12A",
                capacity=8,
            ),
        )
        assert result.status == "occupied"

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = self._use_case(
            InMemoryTableRepository(), InMemoryTableZoneRepository(), FakeOutboxWriter()
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateTableRequestDTO(
                    table_id=TABLE_ID,
                    branch_id=BRANCH_ID,
                    table_zone_id=TABLE_ZONE_ID,
                    table_number="1",
                    capacity=2,
                ),
            )

    async def test_raises_not_found_when_the_table_belongs_to_a_different_branch(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(branch_id=OTHER_BRANCH_ID)})
        use_case = self._use_case(table_repo, InMemoryTableZoneRepository(), FakeOutboxWriter())

        with pytest.raises(TableNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateTableRequestDTO(
                    table_id=TABLE_ID,
                    branch_id=BRANCH_ID,
                    table_zone_id=TABLE_ZONE_ID,
                    table_number="1",
                    capacity=2,
                ),
            )

    async def test_changing_zone_re_verifies_it_belongs_to_the_same_branch(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        table_zone_repo = InMemoryTableZoneRepository(
            {OTHER_TABLE_ZONE_ID: _table_zone(id=OTHER_TABLE_ZONE_ID, branch_id=OTHER_BRANCH_ID)}
        )
        use_case = self._use_case(table_repo, table_zone_repo, FakeOutboxWriter())

        with pytest.raises(TableZoneNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateTableRequestDTO(
                    table_id=TABLE_ID,
                    branch_id=BRANCH_ID,
                    table_zone_id=OTHER_TABLE_ZONE_ID,
                    table_number="12A",
                    capacity=4,
                ),
            )

    async def test_changing_zone_to_a_valid_same_branch_zone_succeeds(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        table_zone_repo = InMemoryTableZoneRepository(
            {OTHER_TABLE_ZONE_ID: _table_zone(id=OTHER_TABLE_ZONE_ID, name="Bar")}
        )
        use_case = self._use_case(table_repo, table_zone_repo, FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            UpdateTableRequestDTO(
                table_id=TABLE_ID,
                branch_id=BRANCH_ID,
                table_zone_id=OTHER_TABLE_ZONE_ID,
                table_number="12A",
                capacity=4,
            ),
        )
        assert result.table_zone_id == OTHER_TABLE_ZONE_ID

    async def test_renaming_to_a_sibling_tables_number_is_rejected(self) -> None:
        other_table_id = "01ARZ3NDEKTSV4RRFFQ6TABLE2"
        table_repo = InMemoryTableRepository(
            {
                TABLE_ID: _table(table_number="ToRename"),
                other_table_id: _table(id=other_table_id, table_number="Existing"),
            }
        )
        use_case = self._use_case(table_repo, InMemoryTableZoneRepository(), FakeOutboxWriter())

        with pytest.raises(TableNumberConflictError):
            await use_case.execute(
                TENANT_ID,
                UpdateTableRequestDTO(
                    table_id=TABLE_ID,
                    branch_id=BRANCH_ID,
                    table_zone_id=TABLE_ZONE_ID,
                    table_number="Existing",
                    capacity=4,
                ),
            )

    async def test_renaming_to_its_own_current_number_is_not_a_conflict(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(table_number="12A")})
        use_case = self._use_case(table_repo, InMemoryTableZoneRepository(), FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            UpdateTableRequestDTO(
                table_id=TABLE_ID,
                branch_id=BRANCH_ID,
                table_zone_id=TABLE_ZONE_ID,
                table_number="12A",
                capacity=10,
            ),
        )
        assert result.table_number == "12A"
        assert result.capacity == 10


class TestChangeTableStatusUseCase:
    def _use_case(self, table_repo, branch_repo, resolved, outbox) -> ChangeTableStatusUseCase:
        return ChangeTableStatusUseCase(
            session_factory=_session_factory(),
            table_repository_factory=lambda _s: table_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_a_tenant_wide_manage_holder_can_change_status(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.AVAILABLE)})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        outbox = FakeOutboxWriter()
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.manage"}))
        use_case = self._use_case(table_repo, branch_repo, resolved, outbox)

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeTableStatusRequestDTO(table_id=TABLE_ID, status="occupied"),
        )

        assert result.status == "occupied"
        assert len(outbox.published) == 1
        event = outbox.published[0][1]
        assert isinstance(event, TableStatusChanged)
        assert event.previous_status == "available"
        assert event.new_status == "occupied"

    async def test_a_branch_scoped_manage_holder_can_change_status_at_their_own_branch(
        self,
    ) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"table.manage"})})
        use_case = self._use_case(table_repo, branch_repo, resolved, FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeTableStatusRequestDTO(table_id=TABLE_ID, status="cleaning"),
        )
        assert result.status == "cleaning"

    async def test_a_branch_scoped_manage_holder_cannot_change_status_at_a_different_branch(
        self,
    ) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(branch_id=OTHER_BRANCH_ID)})
        branch_repo = InMemoryBranchRepository(
            {OTHER_BRANCH_ID: _branch(id=OTHER_BRANCH_ID, name="Uptown")}
        )
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"table.manage"})})
        use_case = self._use_case(table_repo, branch_repo, resolved, FakeOutboxWriter())

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeTableStatusRequestDTO(table_id=TABLE_ID, status="cleaning"),
            )

    async def test_no_grant_at_all_is_denied(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = self._use_case(
            table_repo, branch_repo, ResolvedPermissions(), FakeOutboxWriter()
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeTableStatusRequestDTO(table_id=TABLE_ID, status="cleaning"),
            )

    async def test_raises_not_found_for_an_unknown_table(self) -> None:
        use_case = self._use_case(
            InMemoryTableRepository(),
            InMemoryBranchRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"table.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeTableStatusRequestDTO(table_id=TABLE_ID, status="cleaning"),
            )

    async def test_raises_not_found_for_a_cross_tenant_table(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(tenant_id=OTHER_TENANT_ID)})
        use_case = self._use_case(
            table_repo,
            InMemoryBranchRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"table.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeTableStatusRequestDTO(table_id=TABLE_ID, status="cleaning"),
            )

    async def test_every_valid_status_value_is_accepted(self) -> None:
        for value in ("available", "occupied", "reserved", "cleaning"):
            table_repo = InMemoryTableRepository({TABLE_ID: _table()})
            branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
            resolved = ResolvedPermissions(tenant_wide=frozenset({"table.manage"}))
            use_case = self._use_case(table_repo, branch_repo, resolved, FakeOutboxWriter())

            result = await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeTableStatusRequestDTO(table_id=TABLE_ID, status=value),
            )
            assert result.status == value

    async def test_setting_status_to_its_own_current_value_succeeds(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(status=TableStatus.AVAILABLE)})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.manage"}))
        use_case = self._use_case(table_repo, branch_repo, resolved, FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeTableStatusRequestDTO(table_id=TABLE_ID, status="available"),
        )
        assert result.status == "available"
