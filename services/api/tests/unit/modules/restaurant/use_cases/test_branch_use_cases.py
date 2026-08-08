"""Unit tests for Branch CRUD use cases (Sprint 5 Step 4.2) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    AddressRequestDTO,
    CreateBranchRequestDTO,
    UpdateBranchRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CloseBranchUseCase,
    CreateBranchUseCase,
    GetBranchUseCase,
    ReopenBranchUseCase,
    UpdateBranchUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Address,
    Branch,
    BranchStatus,
    Restaurant,
    RestaurantStatus,
)
from restaurant_os_api.modules.restaurant.domain.events import (
    BranchClosed,
    BranchCreated,
    BranchReopened,
    BranchUpdated,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNameConflictError,
    BranchNotFoundError,
    InvalidBranchStatusTransitionError,
    RestaurantNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryAddressRepository,
    InMemoryBranchRepository,
    InMemoryRestaurantRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"


def _restaurant(**overrides) -> Restaurant:
    defaults = {
        "id": RESTAURANT_ID,
        "tenant_id": TENANT_ID,
        "legal_name": "Acme",
        "display_name": "Acme",
        "default_currency_code": "USD",
        "status": RestaurantStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Restaurant(**defaults)


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


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateBranchUseCase:
    async def test_creates_and_publishes_branch_created(self) -> None:
        restaurant_repo = InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()})
        branch_repo = InMemoryBranchRepository()
        address_repo = InMemoryAddressRepository()
        outbox = FakeOutboxWriter()
        use_case = CreateBranchUseCase(
            session_factory=_session_factory(),
            restaurant_repository_factory=lambda _s: restaurant_repo,
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: address_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

        result = await use_case.execute(
            TENANT_ID, CreateBranchRequestDTO(restaurant_id=RESTAURANT_ID, name="Downtown")
        )

        assert result.status == "active"
        assert result.restaurant_id == RESTAURANT_ID
        assert result.address is None
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], BranchCreated)

    async def test_creating_with_an_address_persists_it(self) -> None:
        restaurant_repo = InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()})
        use_case = CreateBranchUseCase(
            session_factory=_session_factory(),
            restaurant_repository_factory=lambda _s: restaurant_repo,
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            CreateBranchRequestDTO(
                restaurant_id=RESTAURANT_ID,
                name="Downtown",
                address=AddressRequestDTO(line1="1 Main St", city="Springfield"),
            ),
        )

        assert result.address is not None
        assert result.address.line1 == "1 Main St"

    async def test_raises_not_found_for_an_unknown_restaurant(self) -> None:
        use_case = CreateBranchUseCase(
            session_factory=_session_factory(),
            restaurant_repository_factory=lambda _s: InMemoryRestaurantRepository(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(
                TENANT_ID, CreateBranchRequestDTO(restaurant_id=RESTAURANT_ID, name="X")
            )

    async def test_raises_not_found_for_a_cross_tenant_restaurant(self) -> None:
        restaurant_repo = InMemoryRestaurantRepository(
            {RESTAURANT_ID: _restaurant(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = CreateBranchUseCase(
            session_factory=_session_factory(),
            restaurant_repository_factory=lambda _s: restaurant_repo,
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(
                TENANT_ID, CreateBranchRequestDTO(restaurant_id=RESTAURANT_ID, name="X")
            )

    async def test_a_duplicate_name_under_the_same_restaurant_is_rejected(self) -> None:
        restaurant_repo = InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(name="Downtown")})
        use_case = CreateBranchUseCase(
            session_factory=_session_factory(),
            restaurant_repository_factory=lambda _s: restaurant_repo,
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(BranchNameConflictError):
            await use_case.execute(
                TENANT_ID,
                CreateBranchRequestDTO(restaurant_id=RESTAURANT_ID, name="Downtown"),
            )


class TestGetBranchUseCase:
    async def test_returns_the_branch(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = GetBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID)
        assert result.id == BRANCH_ID

    async def test_includes_the_resolved_address(self) -> None:
        address = Address(
            id="01ARZ3NDEKTSV4RRFFQ6ADDR01",
            tenant_id=TENANT_ID,
            created_at=datetime.now(UTC),
            line1="1 Main St",
        )
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(address_id=address.id)})
        address_repo = InMemoryAddressRepository({address.id: address})
        use_case = GetBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: address_repo,
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID)
        assert result.address is not None
        assert result.address.line1 == "1 Main St"

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = GetBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID)

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(tenant_id=OTHER_TENANT_ID)})
        use_case = GetBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID)


class TestUpdateBranchUseCase:
    async def test_updates_name_and_publishes_branch_updated(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        outbox = FakeOutboxWriter()
        use_case = UpdateBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: outbox,
        )

        result = await use_case.execute(
            TENANT_ID, UpdateBranchRequestDTO(branch_id=BRANCH_ID, name="Renamed")
        )

        assert result.name == "Renamed"
        assert isinstance(outbox.published[0][1], BranchUpdated)

    async def test_adding_an_address_creates_and_links_it(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = UpdateBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateBranchRequestDTO(
                branch_id=BRANCH_ID,
                name="Downtown",
                address=AddressRequestDTO(line1="New Address"),
            ),
        )

        assert result.address is not None
        assert result.address.line1 == "New Address"

    async def test_updating_an_existing_address_edits_it_in_place(self) -> None:
        address = Address(
            id="01ARZ3NDEKTSV4RRFFQ6ADDR01",
            tenant_id=TENANT_ID,
            created_at=datetime.now(UTC),
            line1="Old",
        )
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(address_id=address.id)})
        address_repo = InMemoryAddressRepository({address.id: address})
        use_case = UpdateBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: address_repo,
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateBranchRequestDTO(
                branch_id=BRANCH_ID, name="Downtown", address=AddressRequestDTO(line1="New")
            ),
        )

        assert result.address is not None
        assert result.address.id == address.id, "must edit in place, not create a new row"
        assert result.address.line1 == "New"

    async def test_omitting_address_leaves_it_untouched(self) -> None:
        address = Address(
            id="01ARZ3NDEKTSV4RRFFQ6ADDR01",
            tenant_id=TENANT_ID,
            created_at=datetime.now(UTC),
            line1="Keep Me",
        )
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(address_id=address.id)})
        address_repo = InMemoryAddressRepository({address.id: address})
        use_case = UpdateBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: address_repo,
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID, UpdateBranchRequestDTO(branch_id=BRANCH_ID, name="New Name Only")
        )

        assert result.address is not None
        assert result.address.line1 == "Keep Me"

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = UpdateBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, UpdateBranchRequestDTO(branch_id=BRANCH_ID, name="X"))

    async def test_renaming_to_a_sibling_branchs_name_is_rejected(self) -> None:
        other_branch_id = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
        branch_repo = InMemoryBranchRepository(
            {
                BRANCH_ID: _branch(name="ToRename"),
                other_branch_id: _branch(id=other_branch_id, name="Existing"),
            }
        )
        use_case = UpdateBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(BranchNameConflictError):
            await use_case.execute(
                TENANT_ID, UpdateBranchRequestDTO(branch_id=BRANCH_ID, name="Existing")
            )

    async def test_renaming_to_its_own_current_name_is_not_a_conflict(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(name="Downtown")})
        use_case = UpdateBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID, UpdateBranchRequestDTO(branch_id=BRANCH_ID, name="Downtown")
        )
        assert result.name == "Downtown"


class TestCloseBranchUseCase:
    async def test_closes_and_publishes_branch_closed(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(status=BranchStatus.ACTIVE)})
        outbox = FakeOutboxWriter()
        use_case = CloseBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: outbox,
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID)

        assert result.status == "temporarily_closed"
        assert isinstance(outbox.published[0][1], BranchClosed)

    async def test_closing_an_already_closed_branch_is_rejected(self) -> None:
        branch_repo = InMemoryBranchRepository(
            {BRANCH_ID: _branch(status=BranchStatus.TEMPORARILY_CLOSED)}
        )
        use_case = CloseBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(InvalidBranchStatusTransitionError):
            await use_case.execute(TENANT_ID, BRANCH_ID)

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = CloseBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: InMemoryBranchRepository(),
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID)


class TestReopenBranchUseCase:
    async def test_reopens_and_publishes_branch_reopened(self) -> None:
        branch_repo = InMemoryBranchRepository(
            {BRANCH_ID: _branch(status=BranchStatus.TEMPORARILY_CLOSED)}
        )
        outbox = FakeOutboxWriter()
        use_case = ReopenBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: outbox,
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID)

        assert result.status == "active"
        assert isinstance(outbox.published[0][1], BranchReopened)

    async def test_reopening_an_already_active_branch_is_rejected(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(status=BranchStatus.ACTIVE)})
        use_case = ReopenBranchUseCase(
            session_factory=_session_factory(),
            branch_repository_factory=lambda _s: branch_repo,
            address_repository_factory=lambda _s: InMemoryAddressRepository(),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(InvalidBranchStatusTransitionError):
            await use_case.execute(TENANT_ID, BRANCH_ID)
