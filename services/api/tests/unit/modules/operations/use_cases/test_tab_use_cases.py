"""Unit tests for Tab use cases (Sprint 7 Step 3) -- in-memory fakes,
no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.operations.application.dto import CreateTabRequestDTO
from restaurant_os_api.modules.operations.application.use_cases import (
    CloseTabUseCase,
    CreateTabUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import Tab, TabStatus
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidTabStatusTransitionError,
    TabNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    Table,
    TableStatus,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    TableNotFoundError,
)
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeResolveUserPermissionsUseCase,
    InMemoryTabRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import InMemoryBranchRepository, InMemoryTableRepository

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
OTHER_BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABLE1"
TAB_ID = "01ARZ3NDEKTSV4RRFFQ6TAB001"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": "restaurant-1",
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _table(**overrides) -> Table:
    defaults = {
        "id": TABLE_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "table_zone_id": "zone-1",
        "table_number": "5",
        "capacity": 4,
        "status": TableStatus.AVAILABLE,
        "sync_version": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Table(**defaults)


def _tab(**overrides) -> Tab:
    defaults = {
        "id": TAB_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "status": TabStatus.OPEN,
        "opened_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Tab(**defaults)


class TestCreateTabUseCase:
    def _use_case(self, branch_repo, table_repo, tab_repo) -> CreateTabUseCase:
        return CreateTabUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            table_repository_factory=lambda _s: table_repo,
            tab_repository_factory=lambda _s: tab_repo,
        )

    async def test_creates_an_open_tab(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryTableRepository(),
            InMemoryTabRepository(),
        )

        result = await use_case.execute(TENANT_ID, CreateTabRequestDTO(branch_id=BRANCH_ID))

        assert result.status == TabStatus.OPEN.value
        assert result.branch_id == BRANCH_ID

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository(), InMemoryTableRepository(), InMemoryTabRepository()
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, CreateTabRequestDTO(branch_id=BRANCH_ID))

    async def test_raises_not_found_for_a_table_at_a_different_branch(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryTableRepository({TABLE_ID: _table(branch_id=OTHER_BRANCH_ID)}),
            InMemoryTabRepository(),
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(
                TENANT_ID, CreateTabRequestDTO(branch_id=BRANCH_ID, table_id=TABLE_ID)
            )


class TestCloseTabUseCase:
    def _use_case(self, tab_repo, branch_repo, resolved) -> CloseTabUseCase:
        return CloseTabUseCase(
            session_factory=_session_factory(),
            tab_repository_factory=lambda _s: tab_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_closes_an_open_tab(self) -> None:
        use_case = self._use_case(
            InMemoryTabRepository({TAB_ID: _tab()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        result = await use_case.execute(TENANT_ID, "user-1", TAB_ID)

        assert result.status == TabStatus.CLOSED.value

    async def test_raises_invalid_transition_for_an_already_closed_tab(self) -> None:
        use_case = self._use_case(
            InMemoryTabRepository({TAB_ID: _tab(status=TabStatus.CLOSED)}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        with pytest.raises(InvalidTabStatusTransitionError):
            await use_case.execute(TENANT_ID, "user-1", TAB_ID)

    async def test_raises_not_found_for_an_unknown_tab(self) -> None:
        use_case = self._use_case(
            InMemoryTabRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"order.manage"})),
        )

        with pytest.raises(TabNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", TAB_ID)
