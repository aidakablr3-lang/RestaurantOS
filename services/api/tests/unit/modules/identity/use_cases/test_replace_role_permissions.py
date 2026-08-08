"""Unit tests for ReplaceRolePermissionsUseCase -- the delegation ceiling
applies only to the *added* codes; removing a permission from a role
never needs authorization beyond roles.assign itself, since taking
access away is never an escalation.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.dto import ReplaceRolePermissionsRequestDTO
from restaurant_os_api.modules.identity.application.use_cases import (
    ReplaceRolePermissionsUseCase,
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import Role, RoleScope, UserRole
from restaurant_os_api.modules.identity.domain.exceptions import (
    InsufficientGrantAuthorityError,
    RoleNotFoundError,
)
from tests.unit.modules.identity.fakes import (
    InMemoryRolePermissionRepository,
    InMemoryRoleRepository,
    InMemoryUserRoleRepository,
)
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID

NOW = datetime.now(UTC)
ACTOR_ID = "01ARZ3NDEKTSV4RRFFQ6ACTORX"
TARGET_ROLE_ID = "role-branch-manager"
ACTOR_ROLE_ID = "role-actor"


def _grant(user_id: str, role_id: str) -> UserRole:
    return UserRole(
        id=f"grant-{user_id}-{role_id}",
        tenant_id=TENANT_ID,
        user_id=user_id,
        role_id=role_id,
        branch_id=None,
        granted_at=NOW,
        granted_by_user_id=None,
    )


class _Fixture:
    def __init__(self) -> None:
        self.role_repo = InMemoryRoleRepository(
            {
                TARGET_ROLE_ID: Role(
                    id=TARGET_ROLE_ID,
                    tenant_id=TENANT_ID,
                    name="Branch Manager",
                    description=None,
                    default_scope=RoleScope.BRANCH,
                    is_system=True,
                    is_active=True,
                    created_at=NOW,
                ),
                ACTOR_ROLE_ID: Role(
                    id=ACTOR_ROLE_ID,
                    tenant_id=TENANT_ID,
                    name="Actor Role",
                    description=None,
                    default_scope=RoleScope.TENANT,
                    is_system=True,
                    is_active=True,
                    created_at=NOW,
                ),
            }
        )
        self.role_permission_repo = InMemoryRolePermissionRepository()
        self.user_role_repo = InMemoryUserRoleRepository(
            {f"grant-{ACTOR_ID}-{ACTOR_ROLE_ID}": _grant(ACTOR_ID, ACTOR_ROLE_ID)}
        )

    def use_case(self, session_factory) -> ReplaceRolePermissionsUseCase:
        resolve = ResolveUserPermissionsUseCase(
            session_factory=session_factory,
            user_role_repository_factory=lambda _s: self.user_role_repo,
            role_repository_factory=lambda _s: self.role_repo,
            role_permission_repository_factory=lambda _s: self.role_permission_repo,
        )
        return ReplaceRolePermissionsUseCase(
            session_factory=session_factory,
            resolve_user_permissions_use_case=resolve,
            role_repository_factory=lambda _s: self.role_repo,
            role_permission_repository_factory=lambda _s: self.role_permission_repo,
        )


@pytest.fixture
def fixture() -> _Fixture:
    return _Fixture()


async def test_replacing_with_a_subset_of_current_codes_needs_no_extra_authority(
    fixture: _Fixture, session_factory
) -> None:
    """Pure removal: the actor holds none of these permissions
    themselves, but that's fine -- nothing is being added."""
    await fixture.role_permission_repo.replace_for_role(
        TARGET_ROLE_ID, frozenset({"branch.read", "table.read", "table.manage"})
    )
    use_case = fixture.use_case(session_factory)

    await use_case.execute(
        TENANT_ID,
        ReplaceRolePermissionsRequestDTO(
            actor_user_id=ACTOR_ID,
            role_id=TARGET_ROLE_ID,
            permission_codes=frozenset({"branch.read"}),
        ),
    )

    stored = await fixture.role_permission_repo.list_permission_codes_for_role(TARGET_ROLE_ID)
    assert stored == frozenset({"branch.read"})


async def test_adding_a_code_the_actor_does_not_hold_raises(
    fixture: _Fixture, session_factory
) -> None:
    await fixture.role_permission_repo.replace_for_role(TARGET_ROLE_ID, frozenset({"branch.read"}))
    use_case = fixture.use_case(session_factory)

    with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
        await use_case.execute(
            TENANT_ID,
            ReplaceRolePermissionsRequestDTO(
                actor_user_id=ACTOR_ID,
                role_id=TARGET_ROLE_ID,
                permission_codes=frozenset({"branch.read", "menu.manage"}),
            ),
        )
    assert exc_info.value.reason == "delegation"
    # Must not have partially applied.
    stored = await fixture.role_permission_repo.list_permission_codes_for_role(TARGET_ROLE_ID)
    assert stored == frozenset({"branch.read"})


async def test_adding_a_code_the_actor_already_holds_is_allowed(
    fixture: _Fixture, session_factory
) -> None:
    await fixture.role_permission_repo.replace_for_role(ACTOR_ROLE_ID, frozenset({"menu.manage"}))
    await fixture.role_permission_repo.replace_for_role(TARGET_ROLE_ID, frozenset({"branch.read"}))
    use_case = fixture.use_case(session_factory)

    await use_case.execute(
        TENANT_ID,
        ReplaceRolePermissionsRequestDTO(
            actor_user_id=ACTOR_ID,
            role_id=TARGET_ROLE_ID,
            permission_codes=frozenset({"branch.read", "menu.manage"}),
        ),
    )

    stored = await fixture.role_permission_repo.list_permission_codes_for_role(TARGET_ROLE_ID)
    assert stored == frozenset({"branch.read", "menu.manage"})


async def test_replacing_permissions_for_an_unknown_role_raises_not_found(
    fixture: _Fixture, session_factory
) -> None:
    use_case = fixture.use_case(session_factory)

    with pytest.raises(RoleNotFoundError):
        await use_case.execute(
            TENANT_ID,
            ReplaceRolePermissionsRequestDTO(
                actor_user_id=ACTOR_ID,
                role_id="role-does-not-exist",
                permission_codes=frozenset(),
            ),
        )
