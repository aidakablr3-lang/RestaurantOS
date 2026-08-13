"""Unit tests for RevokeUserRoleUseCase (RBAC Foundation Architecture
SS16.1, Commit 5) -- the scope-only ceiling on revocation, and the
session-facing effect (permission_version bump) that makes a revocation
take effect on the very next request.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.dto import RevokeUserRoleRequestDTO
from restaurant_os_api.modules.identity.application.use_cases import (
    ResolveUserPermissionsUseCase,
    RevokeUserRoleUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import (
    Role,
    RoleScope,
    User,
    UserRole,
    UserStatus,
)
from restaurant_os_api.modules.identity.domain.events import UserRoleRevoked
from restaurant_os_api.modules.identity.domain.exceptions import (
    InsufficientGrantAuthorityError,
    UserRoleNotFoundError,
)
from tests.unit.modules.identity.fakes import (
    FakeOutboxWriter,
    InMemoryRolePermissionRepository,
    InMemoryRoleRepository,
    InMemoryUserRepository,
    InMemoryUserRoleRepository,
)
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID

NOW = datetime.now(UTC)
REVOKER_ID = "01ARZ3NDEKTSV4RRFFQ6REVOKR"
TARGET_ID = "01ARZ3NDEKTSV4RRFFQ6TARGET"
BRANCH_A = "01ARZ3NDEKTSV4RRFFQ6BRNCHA"
BRANCH_B = "01ARZ3NDEKTSV4RRFFQ6BRNCHB"

TENANT_OWNER_ROLE_ID = "role-tenant-owner"
BRANCH_MANAGER_ROLE_ID = "role-branch-manager"
WAITER_ROLE_ID = "role-waiter"


def _role(role_id: str) -> Role:
    return Role(
        id=role_id,
        tenant_id=TENANT_ID,
        name=role_id,
        description=None,
        default_scope=RoleScope.BRANCH,
        is_system=True,
        is_active=True,
        created_at=NOW,
    )


def _grant(grant_id: str, user_id: str, role_id: str, *, branch_id: str | None) -> UserRole:
    return UserRole(
        id=grant_id,
        tenant_id=TENANT_ID,
        user_id=user_id,
        role_id=role_id,
        branch_id=branch_id,
        granted_at=NOW,
        granted_by_user_id=None,
    )


class _Fixture:
    def __init__(self) -> None:
        self.role_repo = InMemoryRoleRepository(
            {
                TENANT_OWNER_ROLE_ID: _role(TENANT_OWNER_ROLE_ID),
                BRANCH_MANAGER_ROLE_ID: _role(BRANCH_MANAGER_ROLE_ID),
                WAITER_ROLE_ID: _role(WAITER_ROLE_ID),
            }
        )
        self.role_permission_repo = InMemoryRolePermissionRepository()
        self.user_role_repo = InMemoryUserRoleRepository()
        self.user_repo = InMemoryUserRepository()
        self.outbox = FakeOutboxWriter()

    async def setup_permissions(self) -> None:
        await self.role_permission_repo.replace_for_role(
            TENANT_OWNER_ROLE_ID, frozenset({"roles.assign"})
        )
        await self.role_permission_repo.replace_for_role(
            BRANCH_MANAGER_ROLE_ID, frozenset({"branch.read", "roles.assign"})
        )
        await self.role_permission_repo.replace_for_role(WAITER_ROLE_ID, frozenset({"table.read"}))

    def use_case(self, session_factory) -> RevokeUserRoleUseCase:
        resolve = ResolveUserPermissionsUseCase(
            session_factory=session_factory,
            user_role_repository_factory=lambda _s: self.user_role_repo,
            role_repository_factory=lambda _s: self.role_repo,
            role_permission_repository_factory=lambda _s: self.role_permission_repo,
        )
        return RevokeUserRoleUseCase(
            session_factory=session_factory,
            resolve_user_permissions_use_case=resolve,
            user_role_repository_factory=lambda _s: self.user_role_repo,
            user_repository_factory=lambda _s: self.user_repo,
            outbox_writer_factory=lambda _s: self.outbox,
        )


@pytest.fixture
def fixture() -> _Fixture:
    f = _Fixture()
    for uid in (REVOKER_ID, TARGET_ID):
        f.user_repo._users[uid] = User(
            id=uid,
            tenant_id=TENANT_ID,
            email=f"{uid}@example.com",
            phone=None,
            password_hash="hashed::x",
            pin_hash=None,
            permission_version=1,
            status=UserStatus.ACTIVE,
            created_at=NOW,
        )
    return f


async def test_tenant_owner_can_revoke_any_grant(fixture: _Fixture, session_factory) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", REVOKER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    fixture.user_role_repo._user_roles["target-grant"] = _grant(
        "target-grant", TARGET_ID, WAITER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory)

    await use_case.execute(
        TENANT_ID, RevokeUserRoleRequestDTO(revoker_user_id=REVOKER_ID, user_role_id="target-grant")
    )

    assert await fixture.user_role_repo.get_by_id(TENANT_ID, "target-grant") is None


async def test_revoke_bumps_the_revoked_users_permission_version_immediately(
    fixture: _Fixture, session_factory
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", REVOKER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    fixture.user_role_repo._user_roles["target-grant"] = _grant(
        "target-grant", TARGET_ID, WAITER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory)

    await use_case.execute(
        TENANT_ID, RevokeUserRoleRequestDTO(revoker_user_id=REVOKER_ID, user_role_id="target-grant")
    )

    assert fixture.user_repo._users[TARGET_ID].permission_version == 2


async def test_revoke_publishes_user_role_revoked(fixture: _Fixture, session_factory) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", REVOKER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    fixture.user_role_repo._user_roles["target-grant"] = _grant(
        "target-grant", TARGET_ID, WAITER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory)

    await use_case.execute(
        TENANT_ID, RevokeUserRoleRequestDTO(revoker_user_id=REVOKER_ID, user_role_id="target-grant")
    )

    assert len(fixture.outbox.published) == 1
    _tenant_id, event = fixture.outbox.published[0]
    assert isinstance(event, UserRoleRevoked)
    assert event.user_id == TARGET_ID


async def test_effective_permissions_no_longer_include_a_revoked_grant(
    fixture: _Fixture, session_factory
) -> None:
    """Session-level guarantee: because resolution is always a fresh
    read (no cache), a revoked grant stops applying on the very next
    resolution call -- checked directly here, not merely inferred."""
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", REVOKER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    fixture.user_role_repo._user_roles["target-grant"] = _grant(
        "target-grant", TARGET_ID, WAITER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory)
    resolve = ResolveUserPermissionsUseCase(
        session_factory=session_factory,
        user_role_repository_factory=lambda _s: fixture.user_role_repo,
        role_repository_factory=lambda _s: fixture.role_repo,
        role_permission_repository_factory=lambda _s: fixture.role_permission_repo,
    )

    before = await resolve.execute(TENANT_ID, TARGET_ID)
    assert before.has("table.read", branch_id=BRANCH_A) is True

    await use_case.execute(
        TENANT_ID, RevokeUserRoleRequestDTO(revoker_user_id=REVOKER_ID, user_role_id="target-grant")
    )

    after = await resolve.execute(TENANT_ID, TARGET_ID)
    assert after.has("table.read", branch_id=BRANCH_A) is False


async def test_branch_manager_cannot_revoke_a_grant_at_a_different_branch(
    fixture: _Fixture, session_factory
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["bm-grant"] = _grant(
        "bm-grant", REVOKER_ID, BRANCH_MANAGER_ROLE_ID, branch_id=BRANCH_A
    )
    fixture.user_role_repo._user_roles["target-grant"] = _grant(
        "target-grant", TARGET_ID, WAITER_ROLE_ID, branch_id=BRANCH_B
    )
    use_case = fixture.use_case(session_factory)

    with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
        await use_case.execute(
            TENANT_ID,
            RevokeUserRoleRequestDTO(revoker_user_id=REVOKER_ID, user_role_id="target-grant"),
        )
    assert exc_info.value.reason == "scope"
    assert await fixture.user_role_repo.get_by_id(TENANT_ID, "target-grant") is not None


async def test_branch_manager_can_revoke_a_grant_at_their_own_branch(
    fixture: _Fixture, session_factory
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["bm-grant"] = _grant(
        "bm-grant", REVOKER_ID, BRANCH_MANAGER_ROLE_ID, branch_id=BRANCH_A
    )
    fixture.user_role_repo._user_roles["target-grant"] = _grant(
        "target-grant", TARGET_ID, WAITER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory)

    await use_case.execute(
        TENANT_ID, RevokeUserRoleRequestDTO(revoker_user_id=REVOKER_ID, user_role_id="target-grant")
    )

    assert await fixture.user_role_repo.get_by_id(TENANT_ID, "target-grant") is None


async def test_revoking_an_unknown_grant_raises_not_found(
    fixture: _Fixture, session_factory
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", REVOKER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    use_case = fixture.use_case(session_factory)

    with pytest.raises(UserRoleNotFoundError):
        await use_case.execute(
            TENANT_ID,
            RevokeUserRoleRequestDTO(revoker_user_id=REVOKER_ID, user_role_id="no-such-grant"),
        )


async def test_revoking_an_already_revoked_grant_raises_not_found(
    fixture: _Fixture, session_factory
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", REVOKER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    fixture.user_role_repo._user_roles["target-grant"] = _grant(
        "target-grant", TARGET_ID, WAITER_ROLE_ID, branch_id=BRANCH_A
    )
    await fixture.user_role_repo.revoke(TENANT_ID, "target-grant")
    use_case = fixture.use_case(session_factory)

    with pytest.raises(UserRoleNotFoundError):
        await use_case.execute(
            TENANT_ID,
            RevokeUserRoleRequestDTO(revoker_user_id=REVOKER_ID, user_role_id="target-grant"),
        )
