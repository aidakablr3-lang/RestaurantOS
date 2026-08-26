"""Unit tests for GetInventoryCategoryUseCase (Phase 1 design doc §A.7 --
added so AddInventoryStep.verify() can confirm an inventory item's own
category still exists, not just the item)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.use_cases import GetInventoryCategoryUseCase
from restaurant_os_api.modules.operations.domain.entities import (
    InventoryCategory,
    InventoryCategoryType,
)
from restaurant_os_api.modules.operations.domain.exceptions import InventoryCategoryNotFoundError
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeResolveUserPermissionsUseCase,
    InMemoryInventoryCategoryRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ6OTHERT"
CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6CAT001"
USER_ID = "01ARZ3NDEKTSV4RRFFQ6USER01"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _category(**overrides) -> InventoryCategory:
    defaults = {
        "id": CATEGORY_ID,
        "tenant_id": TENANT_ID,
        "name": "Produce",
        "category_type": InventoryCategoryType.BEVERAGE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return InventoryCategory(**defaults)


def _use_case(
    category_repo, resolved: ResolvedPermissions | None = None
) -> GetInventoryCategoryUseCase:
    return GetInventoryCategoryUseCase(
        session_factory=_session_factory(),
        inventory_category_repository_factory=lambda _s: category_repo,
        resolve_user_permissions=FakeResolveUserPermissionsUseCase(
            resolved=resolved or ResolvedPermissions()
        ),
    )


async def test_returns_the_category() -> None:
    use_case = _use_case(InMemoryInventoryCategoryRepository({CATEGORY_ID: _category()}))

    result = await use_case.execute(TENANT_ID, USER_ID, CATEGORY_ID)

    assert result.id == CATEGORY_ID
    assert result.name == "Produce"


async def test_raises_when_no_category_has_that_id() -> None:
    use_case = _use_case(InMemoryInventoryCategoryRepository({}))

    with pytest.raises(InventoryCategoryNotFoundError):
        await use_case.execute(TENANT_ID, USER_ID, CATEGORY_ID)


async def test_raises_when_the_category_belongs_to_a_different_tenant() -> None:
    category = _category(tenant_id=OTHER_TENANT_ID)
    use_case = _use_case(InMemoryInventoryCategoryRepository({CATEGORY_ID: category}))

    with pytest.raises(InventoryCategoryNotFoundError):
        await use_case.execute(TENANT_ID, USER_ID, CATEGORY_ID)


async def test_beverage_category_needs_no_special_permission() -> None:
    category = _category(category_type=InventoryCategoryType.BEVERAGE)
    use_case = _use_case(
        InMemoryInventoryCategoryRepository({CATEGORY_ID: category}), resolved=ResolvedPermissions()
    )

    result = await use_case.execute(TENANT_ID, USER_ID, CATEGORY_ID)

    assert result.id == CATEGORY_ID


async def test_food_category_requires_inventory_food_read() -> None:
    category = _category(category_type=InventoryCategoryType.FOOD)
    use_case = _use_case(
        InMemoryInventoryCategoryRepository({CATEGORY_ID: category}), resolved=ResolvedPermissions()
    )

    with pytest.raises(PermissionDeniedError):
        await use_case.execute(TENANT_ID, USER_ID, CATEGORY_ID)


async def test_food_category_readable_with_inventory_food_read() -> None:
    category = _category(category_type=InventoryCategoryType.FOOD)
    use_case = _use_case(
        InMemoryInventoryCategoryRepository({CATEGORY_ID: category}),
        resolved=ResolvedPermissions(tenant_wide=frozenset({"inventory_food.read"})),
    )

    result = await use_case.execute(TENANT_ID, USER_ID, CATEGORY_ID)

    assert result.id == CATEGORY_ID
