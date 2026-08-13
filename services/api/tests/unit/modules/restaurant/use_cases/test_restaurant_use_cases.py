"""Unit tests for Restaurant CRUD use cases (Sprint 5 Step 4.1) --
Data Architecture v2.0 SS13: no network/DB access, real business logic
against in-memory fakes.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    CreateRestaurantRequestDTO,
    UpdateRestaurantRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateRestaurantUseCase,
    DiscontinueRestaurantUseCase,
    GetRestaurantUseCase,
    ListRestaurantsUseCase,
    UpdateRestaurantUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import Restaurant, RestaurantStatus
from restaurant_os_api.modules.restaurant.domain.events import (
    RestaurantCreated,
    RestaurantDiscontinued,
    RestaurantUpdated,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    InvalidRestaurantStatusTransitionError,
    RestaurantNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryRestaurantRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"


def _restaurant(**overrides) -> Restaurant:
    defaults = {
        "id": RESTAURANT_ID,
        "tenant_id": TENANT_ID,
        "legal_name": "Acme Restaurants Inc.",
        "display_name": "Acme",
        "default_currency_code": "USD",
        "status": RestaurantStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Restaurant(**defaults)


class TestCreateRestaurantUseCase:
    async def test_creates_and_publishes_restaurant_created(self) -> None:
        repo = InMemoryRestaurantRepository()
        outbox = FakeOutboxWriter()
        use_case = CreateRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
            outbox_writer_factory=lambda _session: outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            CreateRestaurantRequestDTO(
                legal_name="Acme Restaurants Inc.",
                display_name="Acme",
                default_currency_code="USD",
            ),
        )

        assert result.tenant_id == TENANT_ID
        assert result.status == "active"
        assert len(repo._restaurants) == 1
        assert len(outbox.published) == 1
        published_tenant_id, event = outbox.published[0]
        assert published_tenant_id == TENANT_ID
        assert isinstance(event, RestaurantCreated)
        assert event.restaurant_id == result.id


class TestGetRestaurantUseCase:
    async def test_returns_the_restaurant(self) -> None:
        restaurant = _restaurant()
        repo = InMemoryRestaurantRepository({restaurant.id: restaurant})
        use_case = GetRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
        )

        result = await use_case.execute(TENANT_ID, restaurant.id)
        assert result.id == restaurant.id

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        repo = InMemoryRestaurantRepository()
        use_case = GetRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(TENANT_ID, "01ARZ3NDEKTSV4RRFFQ6UNKNWN")

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        restaurant = _restaurant(tenant_id=OTHER_TENANT_ID)
        repo = InMemoryRestaurantRepository({restaurant.id: restaurant})
        use_case = GetRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(TENANT_ID, restaurant.id)


class TestListRestaurantsUseCase:
    async def test_lists_only_the_requested_tenants_restaurants(self) -> None:
        mine = _restaurant(id="01ARZ3NDEKTSV4RRFFQ6MINE01", tenant_id=TENANT_ID)
        theirs = _restaurant(id="01ARZ3NDEKTSV4RRFFQ6THEIR1", tenant_id=OTHER_TENANT_ID)
        repo = InMemoryRestaurantRepository({mine.id: mine, theirs.id: theirs})
        use_case = ListRestaurantsUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
        )

        result = await use_case.execute(TENANT_ID, offset=0, limit=20)

        assert result.total == 1
        assert [r.id for r in result.restaurants] == [mine.id]

    async def test_pagination_fields_pass_through(self) -> None:
        repo = InMemoryRestaurantRepository()
        use_case = ListRestaurantsUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
        )

        result = await use_case.execute(TENANT_ID, offset=10, limit=5)
        assert result.offset == 10
        assert result.limit == 5


class TestUpdateRestaurantUseCase:
    async def test_updates_fields_and_publishes_restaurant_updated(self) -> None:
        restaurant = _restaurant()
        repo = InMemoryRestaurantRepository({restaurant.id: restaurant})
        outbox = FakeOutboxWriter()
        use_case = UpdateRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
            outbox_writer_factory=lambda _session: outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateRestaurantRequestDTO(
                restaurant_id=restaurant.id,
                legal_name="Renamed Inc.",
                display_name="Renamed",
                default_currency_code="EUR",
            ),
        )

        assert result.legal_name == "Renamed Inc."
        assert result.display_name == "Renamed"
        assert result.default_currency_code == "EUR"
        assert result.id == restaurant.id
        assert result.tenant_id == TENANT_ID
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], RestaurantUpdated)

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        repo = InMemoryRestaurantRepository()
        use_case = UpdateRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
            outbox_writer_factory=lambda _session: FakeOutboxWriter(),
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateRestaurantRequestDTO(
                    restaurant_id="01ARZ3NDEKTSV4RRFFQ6UNKNWN",
                    legal_name="X",
                    display_name="X",
                    default_currency_code="USD",
                ),
            )

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        restaurant = _restaurant(tenant_id=OTHER_TENANT_ID)
        repo = InMemoryRestaurantRepository({restaurant.id: restaurant})
        use_case = UpdateRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
            outbox_writer_factory=lambda _session: FakeOutboxWriter(),
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateRestaurantRequestDTO(
                    restaurant_id=restaurant.id,
                    legal_name="Hijacked",
                    display_name="Hijacked",
                    default_currency_code="USD",
                ),
            )


class TestDiscontinueRestaurantUseCase:
    async def test_discontinues_and_publishes_restaurant_discontinued(self) -> None:
        restaurant = _restaurant()
        repo = InMemoryRestaurantRepository({restaurant.id: restaurant})
        outbox = FakeOutboxWriter()
        use_case = DiscontinueRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
            outbox_writer_factory=lambda _session: outbox,
        )

        result = await use_case.execute(TENANT_ID, restaurant.id)

        assert result.status == "discontinued"
        assert isinstance(outbox.published[0][1], RestaurantDiscontinued)

    async def test_discontinuing_an_already_discontinued_restaurant_is_rejected(self) -> None:
        restaurant = _restaurant(status=RestaurantStatus.DISCONTINUED)
        repo = InMemoryRestaurantRepository({restaurant.id: restaurant})
        use_case = DiscontinueRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
            outbox_writer_factory=lambda _session: FakeOutboxWriter(),
        )

        with pytest.raises(InvalidRestaurantStatusTransitionError):
            await use_case.execute(TENANT_ID, restaurant.id)

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        repo = InMemoryRestaurantRepository()
        use_case = DiscontinueRestaurantUseCase(
            session_factory=fake_session_factory_returning(FakeAsyncSession()),
            restaurant_repository_factory=lambda _session: repo,
            outbox_writer_factory=lambda _session: FakeOutboxWriter(),
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(TENANT_ID, "01ARZ3NDEKTSV4RRFFQ6UNKNWN")
