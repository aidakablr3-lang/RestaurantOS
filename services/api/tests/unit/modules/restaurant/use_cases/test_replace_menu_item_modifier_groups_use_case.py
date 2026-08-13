"""Unit tests for ReplaceMenuItemModifierGroupsUseCase (Sprint 5 Step
4.9) -- in-memory fakes, no network/DB access.

Covers the ``PUT /api/v1/menu-items/{id}/modifier-groups`` full-set
replace semantics: atomic replacement (not append), an empty set
clearing every attachment, every referenced ``modifier_group_id``
validated against the caller's own tenant before the replace is
issued, and that a single invalid/cross-tenant id anywhere in the
request fails the whole call (no partial replace).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    ReplaceMenuItemModifierGroupsRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    ReplaceMenuItemModifierGroupsUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    MenuItem,
    ModifierGroup,
    ModifierSelectionType,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuItemNotFoundError,
    ModifierGroupNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    InMemoryMenuItemModifierGroupRepository,
    InMemoryMenuItemRepository,
    InMemoryModifierGroupRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT01"
MENU_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6MITM01"
GROUP_A_ID = "01ARZ3NDEKTSV4RRFFQ6MGRPA1"
GROUP_B_ID = "01ARZ3NDEKTSV4RRFFQ6MGRPB1"
GROUP_C_ID = "01ARZ3NDEKTSV4RRFFQ6MGRPC1"
GROUP_D_ID = "01ARZ3NDEKTSV4RRFFQ6MGRPD1"


def _menu_item(**overrides) -> MenuItem:
    defaults = {
        "id": MENU_ITEM_ID,
        "tenant_id": TENANT_ID,
        "menu_category_id": MENU_CATEGORY_ID,
        "name": "Burger",
        "price_amount": Decimal("9.99"),
        "currency_code": "USD",
        "is_available": True,
        "display_order": 0,
        "created_at": datetime.now(UTC),
        "recipe_id": None,
    }
    defaults.update(overrides)
    return MenuItem(**defaults)


def _modifier_group(**overrides) -> ModifierGroup:
    defaults = {
        "id": GROUP_A_ID,
        "tenant_id": TENANT_ID,
        "name": "Group",
        "selection_type": ModifierSelectionType.SINGLE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ModifierGroup(**defaults)


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _use_case(
    menu_item_repo, modifier_group_repo, attachment_repo
) -> ReplaceMenuItemModifierGroupsUseCase:
    return ReplaceMenuItemModifierGroupsUseCase(
        session_factory=_session_factory(),
        menu_item_repository_factory=lambda _s: menu_item_repo,
        modifier_group_repository_factory=lambda _s: modifier_group_repo,
        menu_item_modifier_group_repository_factory=lambda _s: attachment_repo,
    )


class TestReplaceMenuItemModifierGroupsUseCase:
    async def test_replaces_the_full_set_atomically(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        modifier_group_repo = InMemoryModifierGroupRepository(
            {
                GROUP_A_ID: _modifier_group(id=GROUP_A_ID),
                GROUP_D_ID: _modifier_group(id=GROUP_D_ID),
            }
        )
        attachment_repo = InMemoryMenuItemModifierGroupRepository(
            {MENU_ITEM_ID: frozenset({GROUP_A_ID, "existing-b", "existing-c"})}
        )
        use_case = _use_case(menu_item_repo, modifier_group_repo, attachment_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceMenuItemModifierGroupsRequestDTO(
                menu_item_id=MENU_ITEM_ID, modifier_group_ids=frozenset({GROUP_A_ID, GROUP_D_ID})
            ),
        )

        assert result.modifier_group_ids == frozenset({GROUP_A_ID, GROUP_D_ID})
        assert attachment_repo.replace_calls == [
            (TENANT_ID, MENU_ITEM_ID, frozenset({GROUP_A_ID, GROUP_D_ID}))
        ]
        # The stored attachment set is the new set exactly -- B and C
        # (present before the call) are gone, not merged/appended.
        stored = await attachment_repo.list_modifier_group_ids_for_menu_item(
            TENANT_ID, MENU_ITEM_ID
        )
        assert stored == frozenset({GROUP_A_ID, GROUP_D_ID})

    async def test_an_empty_set_clears_every_attachment(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        attachment_repo = InMemoryMenuItemModifierGroupRepository(
            {MENU_ITEM_ID: frozenset({GROUP_A_ID})}
        )
        use_case = _use_case(menu_item_repo, InMemoryModifierGroupRepository(), attachment_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceMenuItemModifierGroupsRequestDTO(
                menu_item_id=MENU_ITEM_ID, modifier_group_ids=frozenset()
            ),
        )

        assert result.modifier_group_ids == frozenset()
        stored = await attachment_repo.list_modifier_group_ids_for_menu_item(
            TENANT_ID, MENU_ITEM_ID
        )
        assert stored == frozenset()

    async def test_duplicate_ids_in_the_source_collapse_to_one_validation_and_one_row(
        self,
    ) -> None:
        """``frozenset`` construction (schema -> DTO) already collapses
        duplicates before this use case ever sees them -- this test
        locks in that a frozenset with N unique ids validates each
        exactly once, never double-inserting or double-validating."""
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        modifier_group_repo = InMemoryModifierGroupRepository(
            {GROUP_A_ID: _modifier_group(id=GROUP_A_ID)}
        )
        attachment_repo = InMemoryMenuItemModifierGroupRepository()
        use_case = _use_case(menu_item_repo, modifier_group_repo, attachment_repo)

        # Simulates the router's `frozenset(body.modifier_group_ids)`
        # conversion from a JSON list containing the same id twice.
        deduped = frozenset([GROUP_A_ID, GROUP_A_ID])
        assert len(deduped) == 1

        result = await use_case.execute(
            TENANT_ID,
            ReplaceMenuItemModifierGroupsRequestDTO(
                menu_item_id=MENU_ITEM_ID, modifier_group_ids=deduped
            ),
        )

        assert result.modifier_group_ids == frozenset({GROUP_A_ID})
        assert attachment_repo.replace_calls == [(TENANT_ID, MENU_ITEM_ID, frozenset({GROUP_A_ID}))]

    async def test_raises_not_found_for_an_unknown_menu_item(self) -> None:
        use_case = _use_case(
            InMemoryMenuItemRepository(),
            InMemoryModifierGroupRepository(),
            InMemoryMenuItemModifierGroupRepository(),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                ReplaceMenuItemModifierGroupsRequestDTO(
                    menu_item_id=MENU_ITEM_ID, modifier_group_ids=frozenset()
                ),
            )

    async def test_raises_not_found_for_a_cross_tenant_menu_item(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository(
            {MENU_ITEM_ID: _menu_item(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = _use_case(
            menu_item_repo,
            InMemoryModifierGroupRepository(),
            InMemoryMenuItemModifierGroupRepository(),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                ReplaceMenuItemModifierGroupsRequestDTO(
                    menu_item_id=MENU_ITEM_ID, modifier_group_ids=frozenset()
                ),
            )

    async def test_raises_not_found_for_an_invalid_modifier_group(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        attachment_repo = InMemoryMenuItemModifierGroupRepository()
        use_case = _use_case(menu_item_repo, InMemoryModifierGroupRepository(), attachment_repo)

        with pytest.raises(ModifierGroupNotFoundError):
            await use_case.execute(
                TENANT_ID,
                ReplaceMenuItemModifierGroupsRequestDTO(
                    menu_item_id=MENU_ITEM_ID, modifier_group_ids=frozenset({GROUP_A_ID})
                ),
            )

        # No partial replace -- the attachment repository was never called.
        assert attachment_repo.replace_calls == []

    async def test_raises_not_found_for_a_cross_tenant_modifier_group(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        modifier_group_repo = InMemoryModifierGroupRepository(
            {GROUP_A_ID: _modifier_group(id=GROUP_A_ID, tenant_id=OTHER_TENANT_ID)}
        )
        attachment_repo = InMemoryMenuItemModifierGroupRepository()
        use_case = _use_case(menu_item_repo, modifier_group_repo, attachment_repo)

        with pytest.raises(ModifierGroupNotFoundError):
            await use_case.execute(
                TENANT_ID,
                ReplaceMenuItemModifierGroupsRequestDTO(
                    menu_item_id=MENU_ITEM_ID, modifier_group_ids=frozenset({GROUP_A_ID})
                ),
            )
        assert attachment_repo.replace_calls == []

    async def test_one_invalid_id_among_several_valid_ones_fails_the_whole_call(self) -> None:
        """A single bad id anywhere in the set rejects the entire
        request -- no silent partial attachment, and no way to use
        this endpoint to probe for another tenant's modifier groups
        one id at a time."""
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        modifier_group_repo = InMemoryModifierGroupRepository(
            {
                GROUP_A_ID: _modifier_group(id=GROUP_A_ID),
                GROUP_B_ID: _modifier_group(id=GROUP_B_ID),
                # GROUP_C_ID deliberately absent -- invalid reference.
            }
        )
        attachment_repo = InMemoryMenuItemModifierGroupRepository()
        use_case = _use_case(menu_item_repo, modifier_group_repo, attachment_repo)

        with pytest.raises(ModifierGroupNotFoundError):
            await use_case.execute(
                TENANT_ID,
                ReplaceMenuItemModifierGroupsRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    modifier_group_ids=frozenset({GROUP_A_ID, GROUP_B_ID, GROUP_C_ID}),
                ),
            )

        assert attachment_repo.replace_calls == []
