"""Unit tests for GetUserUseCase (Phase 1 design doc §A.4 -- added so
ProvisionTenantStep.verify() can read the just-created Owner back)."""

from __future__ import annotations

import pytest

from restaurant_os_api.modules.identity.application.use_cases import GetUserUseCase
from restaurant_os_api.modules.identity.domain.entities import User
from restaurant_os_api.modules.identity.domain.exceptions import UserNotFoundError
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID, USER_ID


async def test_returns_the_user_when_found(
    session_factory, user_repository, active_user: User
) -> None:
    use_case = GetUserUseCase(session_factory=session_factory, user_repository_factory=lambda _s: user_repository)

    result = await use_case.execute(TENANT_ID, USER_ID)

    assert result.id == USER_ID
    assert result.email == active_user.email
    assert result.status == "active"


async def test_raises_when_the_user_does_not_exist(session_factory, user_repository) -> None:
    use_case = GetUserUseCase(session_factory=session_factory, user_repository_factory=lambda _s: user_repository)

    with pytest.raises(UserNotFoundError):
        await use_case.execute(TENANT_ID, "01ARZ3NDEKTSV4RRFFQ6UNKNWN")


async def test_raises_when_the_user_belongs_to_a_different_tenant(
    session_factory, user_repository
) -> None:
    use_case = GetUserUseCase(session_factory=session_factory, user_repository_factory=lambda _s: user_repository)

    with pytest.raises(UserNotFoundError):
        await use_case.execute("01ARZ3NDEKTSV4RRFFQ6OTHERT", USER_ID)
