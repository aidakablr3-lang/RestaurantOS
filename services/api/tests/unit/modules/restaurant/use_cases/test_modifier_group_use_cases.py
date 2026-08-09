"""Unit tests for ModifierGroup CRUD use cases (Sprint 5 Step 4.9) --
in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    CreateModifierGroupRequestDTO,
    UpdateModifierGroupRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateModifierGroupUseCase,
    GetModifierGroupUseCase,
    ListModifierGroupsUseCase,
    UpdateModifierGroupUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    ModifierGroup,
    ModifierSelectionType,
)
from restaurant_os_api.modules.restaurant.domain.events import ModifierGroupCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import ModifierGroupNotFoundError
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryModifierGroupRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
MODIFIER_GROUP_ID = "01ARZ3NDEKTSV4RRFFQ6MGRP01"


def _modifier_group(**overrides) -> ModifierGroup:
    defaults = {
        "id": MODIFIER_GROUP_ID,
        "tenant_id": TENANT_ID,
        "name": "Size",
        "selection_type": ModifierSelectionType.SINGLE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ModifierGroup(**defaults)


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateModifierGroupUseCase:
    def _use_case(self, modifier_group_repo, outbox) -> CreateModifierGroupUseCase:
        return CreateModifierGroupUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: modifier_group_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_creates_and_publishes_modifier_group_created(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository()
        outbox = FakeOutboxWriter()
        use_case = self._use_case(modifier_group_repo, outbox)

        result = await use_case.execute(
            TENANT_ID, CreateModifierGroupRequestDTO(name="Size", selection_type="single")
        )

        assert result.name == "Size"
        assert result.selection_type == "single"
        assert result.tenant_id == TENANT_ID
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], ModifierGroupCreated)

    async def test_a_duplicate_name_is_allowed(self) -> None:
        """Architecture SS3.1 explicitly declines to enforce
        ModifierGroup name uniqueness -- "Size" legitimately repeats
        across unrelated item families."""
        modifier_group_repo = InMemoryModifierGroupRepository(
            {MODIFIER_GROUP_ID: _modifier_group(name="Size")}
        )
        use_case = self._use_case(modifier_group_repo, FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID, CreateModifierGroupRequestDTO(name="Size", selection_type="multiple")
        )
        assert result.name == "Size"

    async def test_both_selection_types_are_accepted(self) -> None:
        for value in ("single", "multiple"):
            use_case = self._use_case(InMemoryModifierGroupRepository(), FakeOutboxWriter())
            result = await use_case.execute(
                TENANT_ID, CreateModifierGroupRequestDTO(name="Group", selection_type=value)
            )
            assert result.selection_type == value


class TestGetModifierGroupUseCase:
    async def test_returns_the_modifier_group(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {MODIFIER_GROUP_ID: _modifier_group()}
        )
        use_case = GetModifierGroupUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: modifier_group_repo,
        )

        result = await use_case.execute(TENANT_ID, MODIFIER_GROUP_ID)
        assert result.id == MODIFIER_GROUP_ID

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = GetModifierGroupUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: InMemoryModifierGroupRepository(),
        )

        with pytest.raises(ModifierGroupNotFoundError):
            await use_case.execute(TENANT_ID, MODIFIER_GROUP_ID)

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {MODIFIER_GROUP_ID: _modifier_group(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = GetModifierGroupUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: modifier_group_repo,
        )

        with pytest.raises(ModifierGroupNotFoundError):
            await use_case.execute(TENANT_ID, MODIFIER_GROUP_ID)


class TestListModifierGroupsUseCase:
    async def test_lists_only_the_callers_own_tenant(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {
                "g1": _modifier_group(id="g1", name="Size"),
                "g2": _modifier_group(id="g2", name="Spice"),
                "g3": _modifier_group(id="g3", name="Other", tenant_id=OTHER_TENANT_ID),
            }
        )
        use_case = ListModifierGroupsUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: modifier_group_repo,
        )

        result = await use_case.execute(TENANT_ID, offset=0, limit=20)

        assert result.total == 2
        assert {g.name for g in result.modifier_groups} == {"Size", "Spice"}

    async def test_pagination_offset_and_limit(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {f"g{i}": _modifier_group(id=f"g{i}", name=f"G{i}") for i in range(5)}
        )
        use_case = ListModifierGroupsUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: modifier_group_repo,
        )

        page_1 = await use_case.execute(TENANT_ID, offset=0, limit=2)
        page_2 = await use_case.execute(TENANT_ID, offset=2, limit=2)

        assert page_1.total == page_2.total == 5
        ids_page_1 = {g.id for g in page_1.modifier_groups}
        ids_page_2 = {g.id for g in page_2.modifier_groups}
        assert ids_page_1.isdisjoint(ids_page_2)


class TestUpdateModifierGroupUseCase:
    async def test_updates_name_and_selection_type(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {MODIFIER_GROUP_ID: _modifier_group()}
        )
        use_case = UpdateModifierGroupUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: modifier_group_repo,
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateModifierGroupRequestDTO(
                modifier_group_id=MODIFIER_GROUP_ID, name="Renamed", selection_type="multiple"
            ),
        )

        assert result.name == "Renamed"
        assert result.selection_type == "multiple"

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = UpdateModifierGroupUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: InMemoryModifierGroupRepository(),
        )

        with pytest.raises(ModifierGroupNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateModifierGroupRequestDTO(
                    modifier_group_id=MODIFIER_GROUP_ID, name="X", selection_type="single"
                ),
            )

    async def test_renaming_to_a_sibling_groups_name_is_not_a_conflict(self) -> None:
        other_group_id = "01ARZ3NDEKTSV4RRFFQ6MGRP02"
        modifier_group_repo = InMemoryModifierGroupRepository(
            {
                MODIFIER_GROUP_ID: _modifier_group(name="ToRename"),
                other_group_id: _modifier_group(id=other_group_id, name="Existing"),
            }
        )
        use_case = UpdateModifierGroupUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: modifier_group_repo,
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateModifierGroupRequestDTO(
                modifier_group_id=MODIFIER_GROUP_ID, name="Existing", selection_type="single"
            ),
        )
        assert result.name == "Existing"
