"""Unit tests for CommitMenuImportUseCase -- in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    CommitMenuImportRequestDTO,
    MenuImportCommitRowDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import CommitMenuImportUseCase
from restaurant_os_api.modules.restaurant.domain.entities import (
    MenuCategory,
    Restaurant,
    RestaurantStatus,
)
from restaurant_os_api.modules.restaurant.domain.events import MenuCategoryCreated, MenuItemCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuImportInvalidRowError,
    RestaurantNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryMenuCategoryRepository,
    InMemoryMenuItemRepository,
    InMemoryRestaurantRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
EXISTING_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT01"


def _restaurant(**overrides: object) -> Restaurant:
    defaults: dict[str, object] = {
        "id": RESTAURANT_ID,
        "tenant_id": TENANT_ID,
        "legal_name": "R",
        "display_name": "R",
        "default_currency_code": "INR",
        "status": RestaurantStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Restaurant(**defaults)  # type: ignore[arg-type]


def _existing_category(**overrides: object) -> MenuCategory:
    defaults: dict[str, object] = {
        "id": EXISTING_CATEGORY_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Soups",
        "display_order": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return MenuCategory(**defaults)  # type: ignore[arg-type]


def _use_case(
    *,
    restaurants: dict[str, Restaurant] | None = None,
    categories: dict[str, MenuCategory] | None = None,
    outbox: FakeOutboxWriter | None = None,
) -> tuple[
    CommitMenuImportUseCase,
    InMemoryMenuCategoryRepository,
    InMemoryMenuItemRepository,
    FakeOutboxWriter,
]:
    session = FakeAsyncSession()
    category_repo = InMemoryMenuCategoryRepository(categories)
    item_repo = InMemoryMenuItemRepository()
    outbox_writer = outbox or FakeOutboxWriter()
    resolved_restaurants = {RESTAURANT_ID: _restaurant()} if restaurants is None else restaurants
    use_case = CommitMenuImportUseCase(
        session_factory=fake_session_factory_returning(session),
        restaurant_repository_factory=lambda _s: InMemoryRestaurantRepository(resolved_restaurants),
        menu_category_repository_factory=lambda _s: category_repo,
        menu_item_repository_factory=lambda _s: item_repo,
        outbox_writer_factory=lambda _s: outbox_writer,
    )
    return use_case, category_repo, item_repo, outbox_writer


async def test_raises_when_restaurant_does_not_exist() -> None:
    use_case, *_ = _use_case(restaurants={})
    with pytest.raises(RestaurantNotFoundError):
        await use_case.execute(
            TENANT_ID,
            CommitMenuImportRequestDTO(
                restaurant_id=RESTAURANT_ID,
                rows=[
                    MenuImportCommitRowDTO(
                        category="Soups", name="Tomato Soup", price_amount=Decimal("90.00")
                    )
                ],
            ),
        )


@pytest.mark.parametrize(
    ("category", "name", "price"),
    [
        ("", "Tomato Soup", Decimal("90.00")),
        ("Soups", "", Decimal("90.00")),
        ("Soups", "Tomato Soup", Decimal("0.00")),
        ("Soups", "Tomato Soup", Decimal("-10.00")),
    ],
)
async def test_raises_on_invalid_row_before_persisting_anything(
    category: str, name: str, price: Decimal
) -> None:
    use_case, category_repo, item_repo, _ = _use_case()
    with pytest.raises(MenuImportInvalidRowError):
        await use_case.execute(
            TENANT_ID,
            CommitMenuImportRequestDTO(
                restaurant_id=RESTAURANT_ID,
                rows=[MenuImportCommitRowDTO(category=category, name=name, price_amount=price)],
            ),
        )
    assert (await category_repo.list_for_restaurant(TENANT_ID, RESTAURANT_ID, offset=0, limit=100))[
        1
    ] == 0
    assert item_repo._menu_items == {}  # noqa: SLF001 -- verifying nothing was persisted at all


async def test_creates_a_new_category_and_item() -> None:
    use_case, category_repo, item_repo, outbox = _use_case(categories={})
    result = await use_case.execute(
        TENANT_ID,
        CommitMenuImportRequestDTO(
            restaurant_id=RESTAURANT_ID,
            rows=[
                MenuImportCommitRowDTO(
                    category="Soups", name="Tomato Soup", price_amount=Decimal("90.00")
                )
            ],
        ),
    )

    assert result.categories_created == 1
    assert result.items_created == 1

    categories, total = await category_repo.list_for_restaurant(
        TENANT_ID, RESTAURANT_ID, offset=0, limit=100
    )
    assert total == 1
    assert categories[0].name == "Soups"

    items, item_total = await item_repo.list_for_category(
        TENANT_ID, categories[0].id, offset=0, limit=100
    )
    assert item_total == 1
    assert items[0].name == "Tomato Soup"
    assert items[0].price_amount == Decimal("90.00")
    assert items[0].currency_code == "INR"

    event_types = [type(event).__name__ for _, event in outbox.published]
    assert event_types == [MenuCategoryCreated.__name__, MenuItemCreated.__name__]


async def test_reuses_an_existing_category_case_insensitively() -> None:
    use_case, category_repo, item_repo, outbox = _use_case(
        categories={EXISTING_CATEGORY_ID: _existing_category(name="Soups")}
    )
    result = await use_case.execute(
        TENANT_ID,
        CommitMenuImportRequestDTO(
            restaurant_id=RESTAURANT_ID,
            rows=[
                MenuImportCommitRowDTO(
                    category="SOUPS", name="Tomato Soup", price_amount=Decimal("90.00")
                )
            ],
        ),
    )

    assert result.categories_created == 0
    assert result.items_created == 1

    _, category_total = await category_repo.list_for_restaurant(
        TENANT_ID, RESTAURANT_ID, offset=0, limit=100
    )
    assert category_total == 1  # no duplicate created

    items, _ = await item_repo.list_for_category(
        TENANT_ID, EXISTING_CATEGORY_ID, offset=0, limit=100
    )
    assert len(items) == 1

    event_types = [type(event).__name__ for _, event in outbox.published]
    assert event_types == [
        MenuItemCreated.__name__
    ]  # no MenuCategoryCreated -- reused, not created


async def test_two_rows_with_the_same_new_category_create_only_one_category() -> None:
    use_case, category_repo, item_repo, _ = _use_case(categories={})
    result = await use_case.execute(
        TENANT_ID,
        CommitMenuImportRequestDTO(
            restaurant_id=RESTAURANT_ID,
            rows=[
                MenuImportCommitRowDTO(
                    category="Soups", name="Tomato Soup", price_amount=Decimal("90.00")
                ),
                MenuImportCommitRowDTO(
                    category="soups", name="Sweet Corn Soup", price_amount=Decimal("100.00")
                ),
            ],
        ),
    )

    assert result.categories_created == 1
    assert result.items_created == 2

    categories, total = await category_repo.list_for_restaurant(
        TENANT_ID, RESTAURANT_ID, offset=0, limit=100
    )
    assert total == 1
    items, _ = await item_repo.list_for_category(TENANT_ID, categories[0].id, offset=0, limit=100)
    assert {i.name for i in items} == {"Tomato Soup", "Sweet Corn Soup"}


async def test_folds_portion_label_into_the_item_name() -> None:
    use_case, category_repo, item_repo, _ = _use_case(categories={})
    await use_case.execute(
        TENANT_ID,
        CommitMenuImportRequestDTO(
            restaurant_id=RESTAURANT_ID,
            rows=[
                MenuImportCommitRowDTO(
                    category="Starters",
                    name="Chicken Kebab",
                    price_amount=Decimal("150.00"),
                    portion_label="Half",
                ),
                MenuImportCommitRowDTO(
                    category="Starters",
                    name="Chicken Kebab",
                    price_amount=Decimal("280.00"),
                    portion_label="Full",
                ),
                MenuImportCommitRowDTO(
                    category="Starters", name="Paneer Tikka", price_amount=Decimal("180.00")
                ),
            ],
        ),
    )

    categories, _ = await category_repo.list_for_restaurant(
        TENANT_ID, RESTAURANT_ID, offset=0, limit=100
    )
    items, _ = await item_repo.list_for_category(TENANT_ID, categories[0].id, offset=0, limit=100)
    names = {i.name for i in items}
    assert names == {"Chicken Kebab — Half", "Chicken Kebab — Full", "Paneer Tikka"}
