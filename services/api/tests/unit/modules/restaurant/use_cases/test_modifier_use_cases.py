"""Unit tests for Modifier CRUD use cases (Sprint 5 Step 4.9) --
in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    CreateModifierRequestDTO,
    UpdateModifierRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateModifierUseCase,
    GetModifierUseCase,
    ListModifiersUseCase,
    UpdateModifierUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Modifier,
    ModifierGroup,
    ModifierSelectionType,
)
from restaurant_os_api.modules.restaurant.domain.events import ModifierCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    ModifierGroupNotFoundError,
    ModifierNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    InMemoryModifierGroupRepository,
    InMemoryModifierRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
MODIFIER_GROUP_ID = "01ARZ3NDEKTSV4RRFFQ6MGRP01"
OTHER_MODIFIER_GROUP_ID = "01ARZ3NDEKTSV4RRFFQ6MGRP02"
MODIFIER_ID = "01ARZ3NDEKTSV4RRFFQ6MODF01"


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


def _modifier(**overrides) -> Modifier:
    defaults = {
        "id": MODIFIER_ID,
        "tenant_id": TENANT_ID,
        "modifier_group_id": MODIFIER_GROUP_ID,
        "name": "Large",
        "price_delta": Decimal("1.50"),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Modifier(**defaults)


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateModifierUseCase:
    def _use_case(self, modifier_group_repo, modifier_repo, outbox) -> CreateModifierUseCase:
        return CreateModifierUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: modifier_group_repo,
            modifier_repository_factory=lambda _s: modifier_repo,
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_creates_and_publishes_modifier_created(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {MODIFIER_GROUP_ID: _modifier_group()}
        )
        modifier_repo = InMemoryModifierRepository()
        outbox = FakeOutboxWriter()
        use_case = self._use_case(modifier_group_repo, modifier_repo, outbox)

        result = await use_case.execute(
            TENANT_ID,
            CreateModifierRequestDTO(
                modifier_group_id=MODIFIER_GROUP_ID, name="Large", price_delta=Decimal("1.50")
            ),
        )

        assert result.name == "Large"
        assert result.modifier_group_id == MODIFIER_GROUP_ID
        assert result.price_delta == Decimal("1.50")
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], ModifierCreated)

    async def test_price_delta_may_be_negative(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {MODIFIER_GROUP_ID: _modifier_group()}
        )
        use_case = self._use_case(
            modifier_group_repo, InMemoryModifierRepository(), FakeOutboxWriter()
        )

        result = await use_case.execute(
            TENANT_ID,
            CreateModifierRequestDTO(
                modifier_group_id=MODIFIER_GROUP_ID,
                name="No Cheese",
                price_delta=Decimal("-0.50"),
            ),
        )
        assert result.price_delta == Decimal("-0.50")

    async def test_raises_not_found_for_an_unknown_group(self) -> None:
        use_case = self._use_case(
            InMemoryModifierGroupRepository(), InMemoryModifierRepository(), FakeOutboxWriter()
        )

        with pytest.raises(ModifierGroupNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateModifierRequestDTO(modifier_group_id=MODIFIER_GROUP_ID, name="Large"),
            )

    async def test_raises_not_found_for_a_cross_tenant_group(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {MODIFIER_GROUP_ID: _modifier_group(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = self._use_case(
            modifier_group_repo, InMemoryModifierRepository(), FakeOutboxWriter()
        )

        with pytest.raises(ModifierGroupNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreateModifierRequestDTO(modifier_group_id=MODIFIER_GROUP_ID, name="Large"),
            )

    async def test_duplicate_names_within_the_same_group_are_allowed(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {MODIFIER_GROUP_ID: _modifier_group()}
        )
        modifier_repo = InMemoryModifierRepository({MODIFIER_ID: _modifier(name="Large")})
        use_case = self._use_case(modifier_group_repo, modifier_repo, FakeOutboxWriter())

        result = await use_case.execute(
            TENANT_ID, CreateModifierRequestDTO(modifier_group_id=MODIFIER_GROUP_ID, name="Large")
        )
        assert result.name == "Large"


class TestGetModifierUseCase:
    async def test_returns_the_modifier(self) -> None:
        modifier_repo = InMemoryModifierRepository({MODIFIER_ID: _modifier()})
        use_case = GetModifierUseCase(
            session_factory=_session_factory(), modifier_repository_factory=lambda _s: modifier_repo
        )

        result = await use_case.execute(TENANT_ID, MODIFIER_GROUP_ID, MODIFIER_ID)
        assert result.id == MODIFIER_ID

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = GetModifierUseCase(
            session_factory=_session_factory(),
            modifier_repository_factory=lambda _s: InMemoryModifierRepository(),
        )

        with pytest.raises(ModifierNotFoundError):
            await use_case.execute(TENANT_ID, MODIFIER_GROUP_ID, MODIFIER_ID)

    async def test_raises_not_found_for_a_cross_tenant_id(self) -> None:
        modifier_repo = InMemoryModifierRepository(
            {MODIFIER_ID: _modifier(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = GetModifierUseCase(
            session_factory=_session_factory(), modifier_repository_factory=lambda _s: modifier_repo
        )

        with pytest.raises(ModifierNotFoundError):
            await use_case.execute(TENANT_ID, MODIFIER_GROUP_ID, MODIFIER_ID)

    async def test_raises_not_found_when_the_modifier_belongs_to_a_different_group(self) -> None:
        modifier_repo = InMemoryModifierRepository(
            {MODIFIER_ID: _modifier(modifier_group_id=OTHER_MODIFIER_GROUP_ID)}
        )
        use_case = GetModifierUseCase(
            session_factory=_session_factory(), modifier_repository_factory=lambda _s: modifier_repo
        )

        with pytest.raises(ModifierNotFoundError):
            await use_case.execute(TENANT_ID, MODIFIER_GROUP_ID, MODIFIER_ID)


class TestListModifiersUseCase:
    async def test_lists_only_the_requested_groups_modifiers(self) -> None:
        modifier_group_repo = InMemoryModifierGroupRepository(
            {MODIFIER_GROUP_ID: _modifier_group()}
        )
        modifier_repo = InMemoryModifierRepository(
            {
                "m1": _modifier(id="m1", name="Small"),
                "m2": _modifier(id="m2", name="Large"),
                "m3": _modifier(id="m3", name="Other", modifier_group_id=OTHER_MODIFIER_GROUP_ID),
            }
        )
        use_case = ListModifiersUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: modifier_group_repo,
            modifier_repository_factory=lambda _s: modifier_repo,
        )

        result = await use_case.execute(TENANT_ID, MODIFIER_GROUP_ID)

        assert {m.name for m in result} == {"Small", "Large"}

    async def test_raises_not_found_for_an_unknown_group(self) -> None:
        use_case = ListModifiersUseCase(
            session_factory=_session_factory(),
            modifier_group_repository_factory=lambda _s: InMemoryModifierGroupRepository(),
            modifier_repository_factory=lambda _s: InMemoryModifierRepository(),
        )

        with pytest.raises(ModifierGroupNotFoundError):
            await use_case.execute(TENANT_ID, MODIFIER_GROUP_ID)


class TestUpdateModifierUseCase:
    async def test_updates_name_and_price_delta(self) -> None:
        modifier_repo = InMemoryModifierRepository({MODIFIER_ID: _modifier()})
        use_case = UpdateModifierUseCase(
            session_factory=_session_factory(), modifier_repository_factory=lambda _s: modifier_repo
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateModifierRequestDTO(
                modifier_id=MODIFIER_ID,
                modifier_group_id=MODIFIER_GROUP_ID,
                name="Extra Large",
                price_delta=Decimal("2.00"),
            ),
        )

        assert result.name == "Extra Large"
        assert result.price_delta == Decimal("2.00")

    async def test_raises_not_found_for_an_unknown_id(self) -> None:
        use_case = UpdateModifierUseCase(
            session_factory=_session_factory(),
            modifier_repository_factory=lambda _s: InMemoryModifierRepository(),
        )

        with pytest.raises(ModifierNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateModifierRequestDTO(
                    modifier_id=MODIFIER_ID,
                    modifier_group_id=MODIFIER_GROUP_ID,
                    name="X",
                    price_delta=Decimal(0),
                ),
            )

    async def test_raises_not_found_when_the_modifier_belongs_to_a_different_group(self) -> None:
        modifier_repo = InMemoryModifierRepository(
            {MODIFIER_ID: _modifier(modifier_group_id=OTHER_MODIFIER_GROUP_ID)}
        )
        use_case = UpdateModifierUseCase(
            session_factory=_session_factory(), modifier_repository_factory=lambda _s: modifier_repo
        )

        with pytest.raises(ModifierNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateModifierRequestDTO(
                    modifier_id=MODIFIER_ID,
                    modifier_group_id=MODIFIER_GROUP_ID,
                    name="X",
                    price_delta=Decimal(0),
                ),
            )
