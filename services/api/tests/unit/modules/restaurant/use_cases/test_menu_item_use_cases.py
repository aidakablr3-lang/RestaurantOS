"""Unit tests for MenuItem CRUD use cases (Sprint 5 Step 4.8) --
in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    CreateMenuItemRequestDTO,
    UpdateMenuItemRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateMenuItemUseCase,
    GetMenuItemUseCase,
    ListMenuItemsUseCase,
    UpdateMenuItemUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import MenuCategory, MenuItem
from restaurant_os_api.modules.restaurant.domain.events import MenuItemCreated, MenuItemUpdated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuCategoryNotFoundError,
    MenuItemNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryMenuCategoryRepository,
    InMemoryMenuItemRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT01"
OTHER_MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT02"
MENU_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6MITM01"


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


def _menu_item(**overrides) -> MenuItem:
    defaults = {
        "id": MENU_ITEM_ID,
        "tenant_id": TENANT_ID,
        "menu_category_id": MENU_CATEGORY_ID,
        "name": "Spring Rolls",
        "price_amount": Decimal("8.99"),
        "currency_code": "USD",
        "is_available": True,
        "display_order": 0,
        "created_at": datetime.now(UTC),
        "recipe_id": None,
    }
    defaults.update(overrides)
    return MenuItem(**defaults)


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateMenuItemUseCase:
    def _use_case(self, menu_category_repo, menu_item_repo, outbox) -> CreateMenuItemUseCase:
        return CreateMenuItemUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
            menu_item_repository_factory=lambda _s: menu_item_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_creates_and_publishes_menu_item_created(self) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()})
        menu_item_repo = InMemoryMenuItemRepository()
        outbox = FakeOutboxWriter()
        use_case = self._use_case(menu_category_repo, menu_item_repo, outbox)

        result = await use_case.execute(
            TENANT_ID,
            CreateMenuItemRequestDTO(
                menu_category_id=MENU_CATEGORY_ID,
                name="Spring Rolls",
                price_amount=Decimal("8.99"),
                currency_code="USD",
                is_available=True,
                display_order=1,
            ),
        )

        assert result.name == "Spring Rolls"
        assert result.menu_category_id == MENU_CATEGORY_ID
        assert result.price_amount == Decimal("8.99")
        assert result.currency_code == "USD"
        assert result.is_available is True
        assert result.recipe_id is None
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], MenuItemCreated)

    async def test_raises_not_found_for_an_unknown_category(self) -> None:
        use_case = self._use_case(
            InMemoryMenuCategoryRepository(), InMemoryMenuItemRepository(), FakeOutboxWriter()
        )

        with pytest.raises(MenuCategoryNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateMenuItemRequestDTO(
                    menu_category_id=MENU_CATEGORY_ID,
                    name="Spring Rolls",
                    price_amount=Decimal("8.99"),
                    currency_code="USD",
                ),
            )

    async def test_raises_not_found_for_a_cross_tenant_category(self) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository(
            {MENU_CATEGORY_ID: _menu_category(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = self._use_case(
            menu_category_repo, InMemoryMenuItemRepository(), FakeOutboxWriter()
        )

        with pytest.raises(MenuCategoryNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateMenuItemRequestDTO(
                    menu_category_id=MENU_CATEGORY_ID,
                    name="Spring Rolls",
                    price_amount=Decimal("8.99"),
                    currency_code="USD",
                ),
            )

    async def test_duplicate_names_within_the_same_category_are_allowed(self) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()})
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item(name="Rolls")})
        use_case = self._use_case(menu_category_repo, menu_item_repo, FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            CreateMenuItemRequestDTO(
                menu_category_id=MENU_CATEGORY_ID,
                name="Rolls",
                price_amount=Decimal("5.00"),
                currency_code="USD",
            ),
        )
        assert result.name == "Rolls"


class TestGetMenuItemUseCase:
    async def test_returns_the_menu_item(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        use_case = GetMenuItemUseCase(
            session_factory=_session_factory(),
            menu_item_repository_factory=lambda _s: menu_item_repo,
        )

        result = await use_case.execute(TENANT_ID, MENU_CATEGORY_ID, MENU_ITEM_ID)
        assert result.id == MENU_ITEM_ID

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = GetMenuItemUseCase(
            session_factory=_session_factory(),
            menu_item_repository_factory=lambda _s: InMemoryMenuItemRepository(),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(TENANT_ID, MENU_CATEGORY_ID, MENU_ITEM_ID)

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository(
            {MENU_ITEM_ID: _menu_item(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = GetMenuItemUseCase(
            session_factory=_session_factory(),
            menu_item_repository_factory=lambda _s: menu_item_repo,
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(TENANT_ID, MENU_CATEGORY_ID, MENU_ITEM_ID)

    async def test_raises_not_found_when_the_item_belongs_to_a_different_category(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository(
            {MENU_ITEM_ID: _menu_item(menu_category_id=OTHER_MENU_CATEGORY_ID)}
        )
        use_case = GetMenuItemUseCase(
            session_factory=_session_factory(),
            menu_item_repository_factory=lambda _s: menu_item_repo,
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(TENANT_ID, MENU_CATEGORY_ID, MENU_ITEM_ID)


class TestListMenuItemsUseCase:
    async def test_lists_only_the_requested_categorys_items_ordered_by_display_order(
        self,
    ) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()})
        menu_item_repo = InMemoryMenuItemRepository(
            {
                "i1": _menu_item(id="i1", name="C", display_order=2),
                "i2": _menu_item(id="i2", name="A", display_order=0),
                "i3": _menu_item(id="i3", name="B", display_order=1),
                "i4": _menu_item(id="i4", name="Other", menu_category_id=OTHER_MENU_CATEGORY_ID),
            }
        )
        use_case = ListMenuItemsUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
            menu_item_repository_factory=lambda _s: menu_item_repo,
        )

        result = await use_case.execute(TENANT_ID, MENU_CATEGORY_ID, offset=0, limit=20)

        assert result.total == 3
        assert [i.name for i in result.menu_items] == ["A", "B", "C"]

    async def test_raises_not_found_for_an_unknown_category(self) -> None:
        use_case = ListMenuItemsUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: InMemoryMenuCategoryRepository(),
            menu_item_repository_factory=lambda _s: InMemoryMenuItemRepository(),
        )

        with pytest.raises(MenuCategoryNotFoundError):
            await use_case.execute(TENANT_ID, MENU_CATEGORY_ID, offset=0, limit=20)

    async def test_pagination_offset_and_limit(self) -> None:
        menu_category_repo = InMemoryMenuCategoryRepository({MENU_CATEGORY_ID: _menu_category()})
        menu_item_repo = InMemoryMenuItemRepository(
            {f"i{i}": _menu_item(id=f"i{i}", name=f"I{i}", display_order=i) for i in range(5)}
        )
        use_case = ListMenuItemsUseCase(
            session_factory=_session_factory(),
            menu_category_repository_factory=lambda _s: menu_category_repo,
            menu_item_repository_factory=lambda _s: menu_item_repo,
        )

        page_1 = await use_case.execute(TENANT_ID, MENU_CATEGORY_ID, offset=0, limit=2)
        page_2 = await use_case.execute(TENANT_ID, MENU_CATEGORY_ID, offset=2, limit=2)

        assert page_1.total == page_2.total == 5
        assert [i.name for i in page_1.menu_items] == ["I0", "I1"]
        assert [i.name for i in page_2.menu_items] == ["I2", "I3"]


class TestUpdateMenuItemUseCase:
    def _use_case(self, menu_item_repo, outbox) -> UpdateMenuItemUseCase:
        return UpdateMenuItemUseCase(
            session_factory=_session_factory(),
            menu_item_repository_factory=lambda _s: menu_item_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_updates_fields_and_publishes_menu_item_updated(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        outbox = FakeOutboxWriter()
        use_case = self._use_case(menu_item_repo, outbox)

        result = await use_case.execute(
            TENANT_ID,
            UpdateMenuItemRequestDTO(
                menu_item_id=MENU_ITEM_ID,
                menu_category_id=MENU_CATEGORY_ID,
                name="Renamed",
                price_amount=Decimal("9.99"),
                currency_code="EUR",
                is_available=False,
                display_order=3,
                station="bar",
            ),
        )

        assert result.name == "Renamed"
        assert result.price_amount == Decimal("9.99")
        assert result.currency_code == "EUR"
        assert result.is_available is False
        assert result.display_order == 3
        assert result.station == "bar"
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], MenuItemUpdated)

    async def test_toggling_availability_is_a_plain_field_update(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item(is_available=True)})
        use_case = self._use_case(menu_item_repo, FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID,
            UpdateMenuItemRequestDTO(
                menu_item_id=MENU_ITEM_ID,
                menu_category_id=MENU_CATEGORY_ID,
                name="Spring Rolls",
                price_amount=Decimal("8.99"),
                currency_code="USD",
                is_available=False,
                display_order=0,
                station="kitchen",
            ),
        )
        assert result.is_available is False

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = self._use_case(InMemoryMenuItemRepository(), FakeOutboxWriter())

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateMenuItemRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    menu_category_id=MENU_CATEGORY_ID,
                    name="X",
                    price_amount=Decimal("1.00"),
                    currency_code="USD",
                    is_available=True,
                    display_order=0,
                    station="kitchen",
                ),
            )

    async def test_raises_not_found_when_the_item_belongs_to_a_different_category(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository(
            {MENU_ITEM_ID: _menu_item(menu_category_id=OTHER_MENU_CATEGORY_ID)}
        )
        use_case = self._use_case(menu_item_repo, FakeOutboxWriter())

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateMenuItemRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    menu_category_id=MENU_CATEGORY_ID,
                    name="X",
                    price_amount=Decimal("1.00"),
                    currency_code="USD",
                    is_available=True,
                    display_order=0,
                    station="kitchen",
                ),
            )
