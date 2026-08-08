"""Unit tests for TableZone CRUD use cases (Sprint 5 Step 4.4) --
in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    CreateTableZoneRequestDTO,
    UpdateTableZoneRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateTableZoneUseCase,
    GetTableZoneUseCase,
    ListTableZonesUseCase,
    UpdateTableZoneUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    TableZone,
)
from restaurant_os_api.modules.restaurant.domain.events import TableZoneCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    TableZoneNameConflictError,
    TableZoneNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryBranchRepository,
    InMemoryTableZoneRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
OTHER_BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
TABLE_ZONE_ID = "01ARZ3NDEKTSV4RRFFQ6TZONE1"


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


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateTableZoneUseCase:
    async def test_creates_and_publishes_table_zone_created(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_zone_repo = InMemoryTableZoneRepository()
        outbox = FakeOutboxWriter()
        use_case = CreateTableZoneUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_zone_repository_factory=lambda _s: table_zone_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            CreateTableZoneRequestDTO(branch_id=BRANCH_ID, name="Patio", display_order=1),
        )

        assert result.name == "Patio"
        assert result.branch_id == BRANCH_ID
        assert result.display_order == 1
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], TableZoneCreated)

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = CreateTableZoneUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            table_zone_repository_factory=lambda _s: InMemoryTableZoneRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID, CreateTableZoneRequestDTO(branch_id=BRANCH_ID, name="Patio")
            )

    async def test_raises_not_found_for_a_cross_tenant_branch(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(tenant_id=OTHER_TENANT_ID)})
        use_case = CreateTableZoneUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_zone_repository_factory=lambda _s: InMemoryTableZoneRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID, CreateTableZoneRequestDTO(branch_id=BRANCH_ID, name="Patio")
            )

    async def test_a_duplicate_name_under_the_same_branch_is_rejected(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_zone_repo = InMemoryTableZoneRepository({TABLE_ZONE_ID: _table_zone(name="Patio")})
        use_case = CreateTableZoneUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_zone_repository_factory=lambda _s: table_zone_repo,
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(TableZoneNameConflictError):
            await use_case.execute(
                TENANT_ID, CreateTableZoneRequestDTO(branch_id=BRANCH_ID, name="Patio")
            )

    async def test_the_same_name_under_a_different_branch_is_allowed(self) -> None:
        branch_repo = InMemoryBranchRepository(
            {
                BRANCH_ID: _branch(),
                OTHER_BRANCH_ID: _branch(id=OTHER_BRANCH_ID, name="Uptown"),
            }
        )
        table_zone_repo = InMemoryTableZoneRepository({TABLE_ZONE_ID: _table_zone(name="Patio")})
        use_case = CreateTableZoneUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_zone_repository_factory=lambda _s: table_zone_repo,
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            CreateTableZoneRequestDTO(branch_id=OTHER_BRANCH_ID, name="Patio"),
        )
        assert result.branch_id == OTHER_BRANCH_ID


class TestGetTableZoneUseCase:
    async def test_returns_the_table_zone(self) -> None:
        table_zone_repo = InMemoryTableZoneRepository({TABLE_ZONE_ID: _table_zone()})
        use_case = GetTableZoneUseCase(
            session_factory=_session_factory(),
            table_zone_repository_factory=lambda _s: table_zone_repo,
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ZONE_ID)
        assert result.id == TABLE_ZONE_ID

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = GetTableZoneUseCase(
            session_factory=_session_factory(),
            table_zone_repository_factory=lambda _s: InMemoryTableZoneRepository(),
        )

        with pytest.raises(TableZoneNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ZONE_ID)

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        table_zone_repo = InMemoryTableZoneRepository(
            {TABLE_ZONE_ID: _table_zone(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = GetTableZoneUseCase(
            session_factory=_session_factory(),
            table_zone_repository_factory=lambda _s: table_zone_repo,
        )

        with pytest.raises(TableZoneNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ZONE_ID)

    async def test_raises_not_found_when_the_table_zone_belongs_to_a_different_branch(
        self,
    ) -> None:
        table_zone_repo = InMemoryTableZoneRepository(
            {TABLE_ZONE_ID: _table_zone(branch_id=OTHER_BRANCH_ID)}
        )
        use_case = GetTableZoneUseCase(
            session_factory=_session_factory(),
            table_zone_repository_factory=lambda _s: table_zone_repo,
        )

        with pytest.raises(TableZoneNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, TABLE_ZONE_ID)


class TestListTableZonesUseCase:
    async def test_lists_only_the_requested_branchs_zones_ordered_by_display_order(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_zone_repo = InMemoryTableZoneRepository(
            {
                "z1": _table_zone(id="z1", name="C", display_order=2),
                "z2": _table_zone(id="z2", name="A", display_order=0),
                "z3": _table_zone(id="z3", name="B", display_order=1),
                "z4": _table_zone(id="z4", name="Other", branch_id=OTHER_BRANCH_ID),
            }
        )
        use_case = ListTableZonesUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_zone_repository_factory=lambda _s: table_zone_repo,
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.total == 3
        assert [tz.name for tz in result.table_zones] == ["A", "B", "C"]

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = ListTableZonesUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            table_zone_repository_factory=lambda _s: InMemoryTableZoneRepository(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

    async def test_pagination_offset_and_limit(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        table_zone_repo = InMemoryTableZoneRepository(
            {f"z{i}": _table_zone(id=f"z{i}", name=f"Z{i}", display_order=i) for i in range(5)}
        )
        use_case = ListTableZonesUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_zone_repository_factory=lambda _s: table_zone_repo,
        )

        page_1 = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=2)
        page_2 = await use_case.execute(TENANT_ID, BRANCH_ID, offset=2, limit=2)

        assert page_1.total == page_2.total == 5
        assert [tz.name for tz in page_1.table_zones] == ["Z0", "Z1"]
        assert [tz.name for tz in page_2.table_zones] == ["Z2", "Z3"]


class TestUpdateTableZoneUseCase:
    async def test_updates_name_and_display_order(self) -> None:
        table_zone_repo = InMemoryTableZoneRepository({TABLE_ZONE_ID: _table_zone()})
        use_case = UpdateTableZoneUseCase(
            session_factory=_session_factory(),
            table_zone_repository_factory=lambda _s: table_zone_repo,
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateTableZoneRequestDTO(
                table_zone_id=TABLE_ZONE_ID, branch_id=BRANCH_ID, name="Renamed", display_order=5
            ),
        )

        assert result.name == "Renamed"
        assert result.display_order == 5

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = UpdateTableZoneUseCase(
            session_factory=_session_factory(),
            table_zone_repository_factory=lambda _s: InMemoryTableZoneRepository(),
        )

        with pytest.raises(TableZoneNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateTableZoneRequestDTO(
                    table_zone_id=TABLE_ZONE_ID, branch_id=BRANCH_ID, name="X", display_order=0
                ),
            )

    async def test_raises_not_found_when_the_table_zone_belongs_to_a_different_branch(
        self,
    ) -> None:
        table_zone_repo = InMemoryTableZoneRepository(
            {TABLE_ZONE_ID: _table_zone(branch_id=OTHER_BRANCH_ID)}
        )
        use_case = UpdateTableZoneUseCase(
            session_factory=_session_factory(),
            table_zone_repository_factory=lambda _s: table_zone_repo,
        )

        with pytest.raises(TableZoneNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateTableZoneRequestDTO(
                    table_zone_id=TABLE_ZONE_ID, branch_id=BRANCH_ID, name="X", display_order=0
                ),
            )

    async def test_renaming_to_a_sibling_zones_name_is_rejected(self) -> None:
        other_zone_id = "01ARZ3NDEKTSV4RRFFQ6TZONE2"
        table_zone_repo = InMemoryTableZoneRepository(
            {
                TABLE_ZONE_ID: _table_zone(name="ToRename"),
                other_zone_id: _table_zone(id=other_zone_id, name="Existing"),
            }
        )
        use_case = UpdateTableZoneUseCase(
            session_factory=_session_factory(),
            table_zone_repository_factory=lambda _s: table_zone_repo,
        )

        with pytest.raises(TableZoneNameConflictError):
            await use_case.execute(
                TENANT_ID,
                UpdateTableZoneRequestDTO(
                    table_zone_id=TABLE_ZONE_ID,
                    branch_id=BRANCH_ID,
                    name="Existing",
                    display_order=0,
                ),
            )

    async def test_renaming_to_its_own_current_name_is_not_a_conflict(self) -> None:
        table_zone_repo = InMemoryTableZoneRepository({TABLE_ZONE_ID: _table_zone(name="Patio")})
        use_case = UpdateTableZoneUseCase(
            session_factory=_session_factory(),
            table_zone_repository_factory=lambda _s: table_zone_repo,
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateTableZoneRequestDTO(
                table_zone_id=TABLE_ZONE_ID, branch_id=BRANCH_ID, name="Patio", display_order=3
            ),
        )
        assert result.name == "Patio"
        assert result.display_order == 3
