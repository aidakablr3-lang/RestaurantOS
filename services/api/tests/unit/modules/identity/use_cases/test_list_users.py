"""Unit tests for ListUsersUseCase -- pagination and tenant isolation,
same shape as test_create_role.py's ListRolesUseCase coverage.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from restaurant_os_api.modules.identity.application.use_cases import ListUsersUseCase
from restaurant_os_api.modules.identity.domain.entities import User, UserStatus
from tests.unit.modules.identity.fakes import InMemoryUserRepository
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID

OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ6OTHERT"
NOW = datetime.now(UTC)


def _user(user_id: str, tenant_id: str, *, offset_seconds: int) -> User:
    return User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id}@example.com",
        phone=None,
        password_hash="hashed::x",
        pin_hash=None,
        permission_version=1,
        status=UserStatus.ACTIVE,
        created_at=NOW + timedelta(seconds=offset_seconds),
    )


@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    return InMemoryUserRepository(
        {
            "u1": _user("u1", TENANT_ID, offset_seconds=1),
            "u2": _user("u2", TENANT_ID, offset_seconds=2),
            "u3": _user("u3", TENANT_ID, offset_seconds=3),
            "other-tenant-user": _user("other-tenant-user", OTHER_TENANT_ID, offset_seconds=1),
        }
    )


async def test_lists_only_the_requested_tenants_users_newest_first(
    user_repo: InMemoryUserRepository, session_factory
) -> None:
    use_case = ListUsersUseCase(
        session_factory=session_factory, user_repository_factory=lambda _s: user_repo
    )

    result = await use_case.execute(TENANT_ID, offset=0, limit=20)

    assert result.total == 3
    assert [u.id for u in result.users] == ["u3", "u2", "u1"]
    assert all(u.tenant_id == TENANT_ID for u in result.users)


async def test_pagination_offset_and_limit(
    user_repo: InMemoryUserRepository, session_factory
) -> None:
    use_case = ListUsersUseCase(
        session_factory=session_factory, user_repository_factory=lambda _s: user_repo
    )

    page = await use_case.execute(TENANT_ID, offset=1, limit=1)

    assert page.total == 3
    assert [u.id for u in page.users] == ["u2"]
    assert page.offset == 1
    assert page.limit == 1
