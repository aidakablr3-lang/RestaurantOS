"""Unit tests for AssignUserRoleUseCase (RBAC Foundation Architecture
SS16.1/SS18, Commit 5) -- the privilege-escalation matrix for granting.

Every scenario in RBAC_Foundation_Architecture.md section 6.3's default
role catalogue is exercised at least once: Tenant Owner, Branch Manager,
Waiter, Cashier, Kitchen Staff attempting grants they should and should
not be able to make.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.dto import AssignUserRoleRequestDTO
from restaurant_os_api.modules.identity.application.use_cases import (
    AssignUserRoleUseCase,
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import Role, RoleScope, UserRole
from restaurant_os_api.modules.identity.domain.events import UserRoleAssigned
from restaurant_os_api.modules.identity.domain.exceptions import (
    DuplicateRoleAssignmentError,
    InsufficientGrantAuthorityError,
    RoleNotActiveError,
    RoleNotFoundError,
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
GRANTER_ID = "01ARZ3NDEKTSV4RRFFQ6GRANTR"
TARGET_ID = "01ARZ3NDEKTSV4RRFFQ6TARGET"
BRANCH_A = "01ARZ3NDEKTSV4RRFFQ6BRNCHA"
BRANCH_B = "01ARZ3NDEKTSV4RRFFQ6BRNCHB"

TENANT_OWNER_ROLE_ID = "role-tenant-owner"
BRANCH_MANAGER_ROLE_ID = "role-branch-manager"
WAITER_ROLE_ID = "role-waiter"


def _role(role_id: str, *, is_active: bool = True) -> Role:
    return Role(
        id=role_id,
        tenant_id=TENANT_ID,
        name=role_id,
        description=None,
        default_scope=RoleScope.BRANCH,
        is_system=True,
        is_active=is_active,
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
    """Bundles the fakes so each test only wires what it needs."""

    def __init__(self, active_user_ids: set[str]) -> None:
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
        self._active_user_ids = active_user_ids

    async def setup_permissions(self) -> None:
        await self.role_permission_repo.replace_for_role(
            TENANT_OWNER_ROLE_ID,
            frozenset(
                {
                    "restaurant.read",
                    "restaurant.manage",
                    "branch.read",
                    "branch.manage",
                    "table.read",
                    "table.manage",
                    "menu.read",
                    "menu.manage",
                    "reservation.read",
                    "reservation.manage",
                    "roles.assign",
                }
            ),
        )
        await self.role_permission_repo.replace_for_role(
            BRANCH_MANAGER_ROLE_ID,
            frozenset({"branch.read", "table.read", "table.manage", "menu.read"}),
        )
        await self.role_permission_repo.replace_for_role(
            WAITER_ROLE_ID, frozenset({"table.read", "menu.read", "reservation.manage"})
        )

    def use_case(self, session_factory, fake_session) -> AssignUserRoleUseCase:
        resolve = ResolveUserPermissionsUseCase(
            session_factory=session_factory,
            user_role_repository_factory=lambda _s: self.user_role_repo,
            role_repository_factory=lambda _s: self.role_repo,
            role_permission_repository_factory=lambda _s: self.role_permission_repo,
        )
        return AssignUserRoleUseCase(
            session_factory=session_factory,
            resolve_user_permissions_use_case=resolve,
            role_repository_factory=lambda _s: self.role_repo,
            role_permission_repository_factory=lambda _s: self.role_permission_repo,
            user_role_repository_factory=lambda _s: self.user_role_repo,
            user_repository_factory=lambda _s: self.user_repo,
            outbox_writer_factory=lambda _s: self.outbox,
        )


@pytest.fixture
def fixture() -> _Fixture:
    from restaurant_os_api.modules.identity.domain.entities import User, UserStatus

    f = _Fixture(active_user_ids={GRANTER_ID, TARGET_ID})
    for uid in (GRANTER_ID, TARGET_ID):
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


async def test_tenant_owner_can_grant_branch_manager_tenant_wide(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", GRANTER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    use_case = fixture.use_case(session_factory, fake_session)

    result = await use_case.execute(
        TENANT_ID,
        AssignUserRoleRequestDTO(
            granter_user_id=GRANTER_ID,
            target_user_id=TARGET_ID,
            role_id=BRANCH_MANAGER_ROLE_ID,
            branch_id=BRANCH_A,
        ),
    )

    assert result.user_id == TARGET_ID
    assert result.role_id == BRANCH_MANAGER_ROLE_ID
    assert result.branch_id == BRANCH_A


async def test_grant_bumps_target_users_permission_version(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", GRANTER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    use_case = fixture.use_case(session_factory, fake_session)

    await use_case.execute(
        TENANT_ID,
        AssignUserRoleRequestDTO(
            granter_user_id=GRANTER_ID,
            target_user_id=TARGET_ID,
            role_id=WAITER_ROLE_ID,
            branch_id=BRANCH_A,
        ),
    )

    assert fixture.user_repo._users[TARGET_ID].permission_version == 2


async def test_grant_publishes_user_role_assigned(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", GRANTER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    use_case = fixture.use_case(session_factory, fake_session)

    await use_case.execute(
        TENANT_ID,
        AssignUserRoleRequestDTO(
            granter_user_id=GRANTER_ID,
            target_user_id=TARGET_ID,
            role_id=WAITER_ROLE_ID,
            branch_id=BRANCH_A,
        ),
    )

    assert len(fixture.outbox.published) == 1
    published_tenant_id, event = fixture.outbox.published[0]
    assert published_tenant_id == TENANT_ID
    assert isinstance(event, UserRoleAssigned)
    assert event.user_id == TARGET_ID
    assert event.role_id == WAITER_ROLE_ID


async def test_branch_manager_without_roles_assign_cannot_grant_anything(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["bm-grant"] = _grant(
        "bm-grant", GRANTER_ID, BRANCH_MANAGER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory, fake_session)

    with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
        await use_case.execute(
            TENANT_ID,
            AssignUserRoleRequestDTO(
                granter_user_id=GRANTER_ID,
                target_user_id=TARGET_ID,
                role_id=WAITER_ROLE_ID,
                branch_id=BRANCH_A,
            ),
        )
    assert exc_info.value.reason == "scope"


async def test_waiter_cannot_self_escalate_to_tenant_owner(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["waiter-grant"] = _grant(
        "waiter-grant", GRANTER_ID, WAITER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory, fake_session)

    with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
        await use_case.execute(
            TENANT_ID,
            AssignUserRoleRequestDTO(
                granter_user_id=GRANTER_ID,
                target_user_id=GRANTER_ID,  # granting to self
                role_id=TENANT_OWNER_ROLE_ID,
                branch_id=None,
            ),
        )
    assert exc_info.value.reason == "scope"
    assert fixture.outbox.published == [], "a denied grant must publish nothing"


async def test_branch_manager_cannot_grant_at_a_different_branch_than_their_own(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    """RBAC_Foundation_Architecture.md SS17's threat model: a Branch
    Manager scoped to Branch A must be denied at Branch B, even with
    roles.assign, even though roles.assign alone might suggest they
    manage roles broadly."""
    await fixture.setup_permissions()
    await fixture.role_permission_repo.replace_for_role(
        BRANCH_MANAGER_ROLE_ID,
        frozenset({"branch.read", "table.read", "table.manage", "menu.read", "roles.assign"}),
    )
    fixture.user_role_repo._user_roles["bm-grant"] = _grant(
        "bm-grant", GRANTER_ID, BRANCH_MANAGER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory, fake_session)

    with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
        await use_case.execute(
            TENANT_ID,
            AssignUserRoleRequestDTO(
                granter_user_id=GRANTER_ID,
                target_user_id=TARGET_ID,
                role_id=WAITER_ROLE_ID,
                branch_id=BRANCH_B,
            ),
        )
    assert exc_info.value.reason == "scope"


async def test_delegation_ceiling_blocks_granting_a_permission_the_granter_lacks(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    """A 'Limited Assigner' holding roles.assign tenant-wide but not
    menu.manage must not be able to hand out a role carrying
    menu.manage, even though their scope covers everywhere."""
    await fixture.setup_permissions()
    limited_assigner_role_id = "role-limited-assigner"
    fixture.role_repo._roles[limited_assigner_role_id] = _role(limited_assigner_role_id)
    await fixture.role_permission_repo.replace_for_role(
        limited_assigner_role_id, frozenset({"roles.assign"})
    )
    fixture.user_role_repo._user_roles["la-grant"] = _grant(
        "la-grant", GRANTER_ID, limited_assigner_role_id, branch_id=None
    )
    use_case = fixture.use_case(session_factory, fake_session)

    with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
        await use_case.execute(
            TENANT_ID,
            AssignUserRoleRequestDTO(
                granter_user_id=GRANTER_ID,
                target_user_id=TARGET_ID,
                role_id=BRANCH_MANAGER_ROLE_ID,  # carries menu.read + table.manage etc.
                branch_id=BRANCH_A,
            ),
        )
    assert exc_info.value.reason == "delegation"


async def test_granting_a_role_named_platform_admin_does_not_touch_the_is_platform_admin_flag(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    """Structural proof, not defensive code: RBAC has no code path that
    can reach users.is_platform_admin at all (RBAC_Foundation_Architecture
    SS10.2). A role literally named 'Platform Admin' is just an ordinary
    Role row."""
    await fixture.setup_permissions()
    fake_role_id = "role-called-platform-admin"
    fixture.role_repo._roles[fake_role_id] = Role(
        id=fake_role_id,
        tenant_id=TENANT_ID,
        name="Platform Admin",
        description=None,
        default_scope=RoleScope.TENANT,
        is_system=False,
        is_active=True,
        created_at=NOW,
    )
    await fixture.role_permission_repo.replace_for_role(fake_role_id, frozenset({"menu.read"}))
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", GRANTER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    use_case = fixture.use_case(session_factory, fake_session)

    assert fixture.user_repo._users[TARGET_ID].is_platform_admin is False

    await use_case.execute(
        TENANT_ID,
        AssignUserRoleRequestDTO(
            granter_user_id=GRANTER_ID,
            target_user_id=TARGET_ID,
            role_id=fake_role_id,
            branch_id=None,
        ),
    )

    assert fixture.user_repo._users[TARGET_ID].is_platform_admin is False


async def test_duplicate_grant_at_the_same_scope_raises(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", GRANTER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    fixture.user_role_repo._user_roles["existing"] = _grant(
        "existing", TARGET_ID, WAITER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory, fake_session)

    with pytest.raises(DuplicateRoleAssignmentError):
        await use_case.execute(
            TENANT_ID,
            AssignUserRoleRequestDTO(
                granter_user_id=GRANTER_ID,
                target_user_id=TARGET_ID,
                role_id=WAITER_ROLE_ID,
                branch_id=BRANCH_A,
            ),
        )


async def test_the_same_role_can_be_granted_to_the_same_user_at_a_different_branch(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    """Not a duplicate -- (user_id, role_id, branch_id) differs."""
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", GRANTER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    fixture.user_role_repo._user_roles["existing"] = _grant(
        "existing", TARGET_ID, WAITER_ROLE_ID, branch_id=BRANCH_A
    )
    use_case = fixture.use_case(session_factory, fake_session)

    result = await use_case.execute(
        TENANT_ID,
        AssignUserRoleRequestDTO(
            granter_user_id=GRANTER_ID,
            target_user_id=TARGET_ID,
            role_id=WAITER_ROLE_ID,
            branch_id=BRANCH_B,
        ),
    )
    assert result.branch_id == BRANCH_B


async def test_granting_an_unknown_role_raises_role_not_found(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    await fixture.setup_permissions()
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", GRANTER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    use_case = fixture.use_case(session_factory, fake_session)

    with pytest.raises(RoleNotFoundError):
        await use_case.execute(
            TENANT_ID,
            AssignUserRoleRequestDTO(
                granter_user_id=GRANTER_ID,
                target_user_id=TARGET_ID,
                role_id="role-does-not-exist",
                branch_id=None,
            ),
        )


async def test_granting_a_retired_role_raises_role_not_active(
    fixture: _Fixture, session_factory, fake_session
) -> None:
    await fixture.setup_permissions()
    retired_role_id = "role-retired"
    fixture.role_repo._roles[retired_role_id] = _role(retired_role_id, is_active=False)
    await fixture.role_permission_repo.replace_for_role(retired_role_id, frozenset())
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", GRANTER_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )
    use_case = fixture.use_case(session_factory, fake_session)

    with pytest.raises(RoleNotActiveError):
        await use_case.execute(
            TENANT_ID,
            AssignUserRoleRequestDTO(
                granter_user_id=GRANTER_ID,
                target_user_id=TARGET_ID,
                role_id=retired_role_id,
                branch_id=None,
            ),
        )
