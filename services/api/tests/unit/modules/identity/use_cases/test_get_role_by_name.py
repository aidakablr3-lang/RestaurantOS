"""Unit tests for GetRoleByNameUseCase (Phase 1 design doc §A.7 -- added
so the staff-creation onboarding steps can resolve a role name to an id
through a use case, never a repository, directly)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.use_cases import GetRoleByNameUseCase
from restaurant_os_api.modules.identity.domain.entities import Role, RoleScope
from restaurant_os_api.modules.identity.domain.exceptions import RoleNotFoundError
from tests.unit.modules.identity.fakes import InMemoryRoleRepository
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID

WAITER_ROLE_ID = "01ARZ3NDEKTSV4RRFFQ6WAITER"


def _waiter_role() -> Role:
    return Role(
        id=WAITER_ROLE_ID,
        tenant_id=TENANT_ID,
        name="Waiter",
        description="Reads tables and the menu; manages reservations and orders.",
        default_scope=RoleScope.BRANCH,
        is_system=True,
        is_active=True,
        created_at=datetime.now(UTC),
    )


async def test_returns_the_role_when_a_matching_name_exists(session_factory) -> None:
    role_repo = InMemoryRoleRepository({WAITER_ROLE_ID: _waiter_role()})
    use_case = GetRoleByNameUseCase(
        session_factory=session_factory, role_repository_factory=lambda _s: role_repo
    )

    result = await use_case.execute(TENANT_ID, "Waiter")

    assert result.id == WAITER_ROLE_ID
    assert result.name == "Waiter"


async def test_raises_when_no_role_has_that_name(session_factory) -> None:
    role_repo = InMemoryRoleRepository({WAITER_ROLE_ID: _waiter_role()})
    use_case = GetRoleByNameUseCase(
        session_factory=session_factory, role_repository_factory=lambda _s: role_repo
    )

    with pytest.raises(RoleNotFoundError):
        await use_case.execute(TENANT_ID, "Nonexistent Role")


async def test_raises_when_the_role_belongs_to_a_different_tenant(session_factory) -> None:
    role = _waiter_role()
    role.tenant_id = "01ARZ3NDEKTSV4RRFFQ6OTHERT"
    role_repo = InMemoryRoleRepository({WAITER_ROLE_ID: role})
    use_case = GetRoleByNameUseCase(
        session_factory=session_factory, role_repository_factory=lambda _s: role_repo
    )

    with pytest.raises(RoleNotFoundError):
        await use_case.execute(TENANT_ID, "Waiter")
