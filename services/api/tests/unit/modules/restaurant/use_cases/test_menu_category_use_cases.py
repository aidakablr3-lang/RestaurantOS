"""Unit tests for MenuCategory CRUD use cases (Sprint 5 Step 4.8) --
in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    CreateMenuCategoryRequestDTO,
    UpdateMenuCategoryRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateMenuCategoryUseCase,
    GetMenuCategoryUseCase,
    ListMenuCategoriesUseCase,
    UpdateMenuCategoryUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    MenuCategory,
    Restaurant,
    RestaurantStatus,
)
from restaurant_os_api.modules.restaurant.domain.events import MenuCategoryCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuCategoryNameConflictError,
    MenuCategoryNotFoundError,
    RestaurantNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryMenuCategoryRepository,
    InMemoryRestaurantRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
OTHER_RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX2"
MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT01"


def _restaurant(**overrides) -> Restaurant:
    defaults = {
        "id": RESTAURANT_ID,
        "tenant_id": TENANT_ID,
        "legal_name": "R",
        "display_name": "R",
        "default_currency_code": "USD",
        "status": RestaurantStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Restaurant(**defaults)


def _menu_category(**overrides) -> MenuCategory:
    defaults = {
        "id": MENU_CATEGORY_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Appetizers",
        "display_order": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return MenuCategory(**defaults)


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateMenuCategoryUseCase:
    def _use_case(self, restaurant_repo, menu_category_repo, outbox) -> CreateMenuCategoryUseCase:
        return CreateMenuCategoryUseCase(
            session_factory=_session_factory(),
            restaurant_repository_factory=lambda _s: restaurant_repo,
            menu_category_repository_factory=lambda _s: menu_category_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_creates_and_publishes_menu_category_created(self) -> None:
        restaurant_repo = InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()})
        menu_category_repo = InMemoryMenuCategoryRepository()
        outbox = FakeOutboxWriter()
        use_case = self._use_case(restaurant_repo, menu_category_repo, outbox)

        result = await use_case.execute(
            TENANT_ID,
            CreateMenuCategoryRequestDTO(
                restaurant_id=RESTAURANT_ID, name="Appetizers", display_order=1
            ),
        )

        assert result.name == "Appetizers"
        assert result.restaurant_id == RESTAURANT_ID
        assert result.display_order == 1
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], MenuCategoryCreated)

    async def test_raises_not_found_for_an_unknown_restaurant(self) -> None:
        use_case = self._use_case(
            InMemoryRestaurantRepository(), InMemoryMenuCategoryRepository(), FakeOutboxWriter()
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateMenuCategoryRequestDTO(restaurant_id=RESTAURANT_ID, name="Appetizers"),
            )

    async def test_raises_not_found_for_a_cross_tenant_restaurant(self) -> None:
        restaurant_repo = InMemoryRestaurantRepository(
            {RESTAURANT_ID: _restaurant(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = self._use_case(
            restaurant_repo, InMemoryMenuCategoryRepository(), FakeOutboxWriter()
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateMenuCategoryRequestDTO(restaurant_id=RESTAURANT_ID, name="Appetizers"),
            )

    async def test_a_duplicate_name_under_the_same_restaurant_is_rejected(self) -> None:
        restaurant_repo = InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()})
        menu_category_repo = InMemoryMenuCategoryRepository(
            {MENU_CATEGORY_ID: _menu_category(name="Appetizers")}
        )
        use_case = self._use_case(restaurant_repo, menu_category_repo, FakeOutboxWriter())

        with pytest.raises(MenuCategoryNameConflictError):
            await use_case.execute(
                TENANT_ID,
                CreateMenuCategoryRequestDTO(restaurant_id=RESTAURANT_ID, name="Appetizers"),
            )

    async def test_the_same_name_under_a_different_restaurant_is_allowed(self) -> None:
        restaurant_repo = InMemoryRestaurantRepository(
            {
                RESTAURANT_ID: _restaurant(),
                OTHER_RESTAURANT_ID: _restaurant(id=OTHER_RESTAURANT_ID, legal_name="Other"),
            }
        )
        menu_category_repo = InMemoryMenuCategoryRepository(
            {MENU_CATEGORY_ID: _menu_category(name="Appetizers")}
        )
        use_case = self._use_case(restaurant_repo, menu_category_repo, FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            CreateMenuCategoryRequestDTO(restaurant_id=OTHER_RESTAURANT_ID, name="Appetizers"),
        )
        assert result.restaurant_id == OTHER_RESTAURANT_ID


class TestGetMenuCategoryUseCase:
    async def test_returns_the_menu_category(self) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()})
        use_case = GetMenuCategoryUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
        )

        result = await use_case.execute(TENANT_ID, RESTAURANT_ID, MENU_CATEGORY_ID)
        assert result.id == MENU_CATEGORY_ID

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = GetMenuCategoryUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: InMemoryMenuCategoryRepository(),
        )

        with pytest.raises(MenuCategoryNotFoundError):
            await use_case.execute(TENANT_ID, RESTAURANT_ID, MENU_CATEGORY_ID)

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository(
            {MENU_CATEGORY_ID: _menu_category(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = GetMenuCategoryUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
        )

        with pytest.raises(MenuCategoryNotFoundError):
            await use_case.execute(TENANT_ID, RESTAURANT_ID, MENU_CATEGORY_ID)

    async def test_raises_not_found_when_the_category_belongs_to_a_different_restaurant(
        self,
    ) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository(
            {MENU_CATEGORY_ID: _menu_category(restaurant_id=OTHER_RESTAURANT_ID)}
        )
        use_case = GetMenuCategoryUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
        )

        with pytest.raises(MenuCategoryNotFoundError):
            await use_case.execute(TENANT_ID, RESTAURANT_ID, MENU_CATEGORY_ID)


class TestListMenuCategoriesUseCase:
    async def test_lists_only_the_requested_restaurants_categories_ordered_by_display_order(
        self,
    ) -> None:
        restaurant_repo = InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()})
        menu_category_repo = InMemoryMenuCategoryRepository(
            {
                "c1": _menu_category(id="c1", name="C", display_order=2),
                "c2": _menu_category(id="c2", name="A", display_order=0),
                "c3": _menu_category(id="c3", name="B", display_order=1),
                "c4": _menu_category(id="c4", name="Other", restaurant_id=OTHER_RESTAURANT_ID),
            }
        )
        use_case = ListMenuCategoriesUseCase(
            session_factory=_session_factory(),
            restaurant_repository_factory=lambda _s: restaurant_repo,
            menu_category_repository_factory=lambda _s: menu_category_repo,
        )

        result = await use_case.execute(TENANT_ID, RESTAURANT_ID, offset=0, limit=20)

        assert result.total == 3
        assert [c.name for c in result.menu_categories] == ["A", "B", "C"]

    async def test_raises_not_found_for_an_unknown_restaurant(self) -> None:
        use_case = ListMenuCategoriesUseCase(
            session_factory=_session_factory(),
            restaurant_repository_factory=lambda _s: InMemoryRestaurantRepository(),
            menu_category_repository_factory=lambda _s: InMemoryMenuCategoryRepository(),
        )

        with pytest.raises(RestaurantNotFoundError):
            await use_case.execute(TENANT_ID, RESTAURANT_ID, offset=0, limit=20)

    async def test_pagination_offset_and_limit(self) -> None:
        restaurant_repo = InMemoryRestaurantRepository({RESTAURANT_ID: _restaurant()})
        menu_category_repo = InMemoryMenuCategoryRepository(
            {f"c{i}": _menu_category(id=f"c{i}", name=f"C{i}", display_order=i) for i in range(5)}
        )
        use_case = ListMenuCategoriesUseCase(
            session_factory=_session_factory(),
            restaurant_repository_factory=lambda _s: restaurant_repo,
            menu_category_repository_factory=lambda _s: menu_category_repo,
        )

        page_1 = await use_case.execute(TENANT_ID, RESTAURANT_ID, offset=0, limit=2)
        page_2 = await use_case.execute(TENANT_ID, RESTAURANT_ID, offset=2, limit=2)

        assert page_1.total == page_2.total == 5
        assert [c.name for c in page_1.menu_categories] == ["C0", "C1"]
        assert [c.name for c in page_2.menu_categories] == ["C2", "C3"]


class TestUpdateMenuCategoryUseCase:
    async def test_updates_name_and_display_order(self) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()})
        use_case = UpdateMenuCategoryUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateMenuCategoryRequestDTO(
                menu_category_id=MENU_CATEGORY_ID,
                restaurant_id=RESTAURANT_ID,
                name="Renamed",
                display_order=5,
            ),
        )

        assert result.name == "Renamed"
        assert result.display_order == 5

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = UpdateMenuCategoryUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: InMemoryMenuCategoryRepository(),
        )

        with pytest.raises(MenuCategoryNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateMenuCategoryRequestDTO(
                    menu_category_id=MENU_CATEGORY_ID,
                    restaurant_id=RESTAURANT_ID,
                    name="X",
                    display_order=0,
                ),
            )

    async def test_raises_not_found_when_the_category_belongs_to_a_different_restaurant(
        self,
    ) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository(
            {MENU_CATEGORY_ID: _menu_category(restaurant_id=OTHER_RESTAURANT_ID)}
        )
        use_case = UpdateMenuCategoryUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
        )

        with pytest.raises(MenuCategoryNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateMenuCategoryRequestDTO(
                    menu_category_id=MENU_CATEGORY_ID,
                    restaurant_id=RESTAURANT_ID,
                    name="X",
                    display_order=0,
                ),
            )

    async def test_renaming_to_a_sibling_categorys_name_is_rejected(self) -> None:
        other_category_id = "01ARZ3NDEKTSV4RRFFQ6MCAT02"
        menu_category_repo = InMemoryMenuCategoryRepository(
            {
                MENU_CATEGORY_ID: _menu_category(name="ToRename"),
                other_category_id: _menu_category(id=other_category_id, name="Existing"),
            }
        )
        use_case = UpdateMenuCategoryUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
        )

        with pytest.raises(MenuCategoryNameConflictError):
            await use_case.execute(
                TENANT_ID,
                UpdateMenuCategoryRequestDTO(
                    menu_category_id=MENU_CATEGORY_ID,
                    restaurant_id=RESTAURANT_ID,
                    name="Existing",
                    display_order=0,
                ),
            )

    async def test_renaming_to_its_own_current_name_is_not_a_conflict(self) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository(
            {MENU_CATEGORY_ID: _menu_category(name="Appetizers")}
        )
        use_case = UpdateMenuCategoryUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateMenuCategoryRequestDTO(
                menu_category_id=MENU_CATEGORY_ID,
                restaurant_id=RESTAURANT_ID,
                name="Appetizers",
                display_order=3,
            ),
        )
        assert result.name == "Appetizers"
        assert result.display_order == 3
