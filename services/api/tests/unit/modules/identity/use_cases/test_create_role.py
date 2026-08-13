"""Unit tests for CreateRoleUseCase -- the delegation ceiling applied to
role authoring itself (a caller must not be able to *define* a role
carrying permissions they don't hold, any more than they could hand out
an existing one), plus the pre-existing name-conflict guard.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.dto import CreateRoleRequestDTO
from restaurant_os_api.modules.identity.application.use_cases import (
    CreateRoleUseCase,
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import Role, RoleScope, UserRole
from restaurant_os_api.modules.identity.domain.events import RoleCreated
from restaurant_os_api.modules.identity.domain.exceptions import (
    InsufficientGrantAuthorityError,
    RoleNameConflictError,
)
from tests.unit.modules.identity.fakes import (
    FakeOutboxWriter,
    InMemoryRolePermissionRepository,
    InMemoryRoleRepository,
    InMemoryUserRoleRepository,
)
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID

NOW = datetime.now(UTC)
CREATOR_ID = "01ARZ3NDEKTSV4RRFFQ6CREATR"
TENANT_OWNER_ROLE_ID = "role-tenant-owner"


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
                TENANT_OWNER_ROLE_ID: Role(
                    id=TENANT_OWNER_ROLE_ID,
                    tenant_id=TENANT_ID,
                    name="Tenant Owner",
                    description=None,
                    default_scope=RoleScope.TENANT,
                    is_system=True,
                    is_active=True,
                    created_at=NOW,
                )
            }
        )
        self.role_permission_repo = InMemoryRolePermissionRepository()
        self.user_role_repo = InMemoryUserRoleRepository()
        self.outbox = FakeOutboxWriter()

    def use_case(self, session_factory) -> CreateRoleUseCase:
        resolve = ResolveUserPermissionsUseCase(
            session_factory=session_factory,
            user_role_repository_factory=lambda _s: self.user_role_repo,
            role_repository_factory=lambda _s: self.role_repo,
            role_permission_repository_factory=lambda _s: self.role_permission_repo,
        )
        return CreateRoleUseCase(
            session_factory=session_factory,
            resolve_user_permissions_use_case=resolve,
            role_repository_factory=lambda _s: self.role_repo,
            role_permission_repository_factory=lambda _s: self.role_permission_repo,
            outbox_writer_factory=lambda _s: self.outbox,
        )


@pytest.fixture
def fixture() -> _Fixture:
    return _Fixture()


async def _grant_owner(fixture: _Fixture) -> None:
    await fixture.role_permission_repo.replace_for_role(
        TENANT_OWNER_ROLE_ID, frozenset({"roles.assign", "menu.manage", "table.read"})
    )
    fixture.user_role_repo._user_roles["owner-grant"] = _grant(
        "owner-grant", CREATOR_ID, TENANT_OWNER_ROLE_ID, branch_id=None
    )


async def test_a_holder_of_all_requested_permissions_can_create_the_role(
    fixture: _Fixture, session_factory
) -> None:
    await _grant_owner(fixture)
    use_case = fixture.use_case(session_factory)

    result = await use_case.execute(
        TENANT_ID,
        CreateRoleRequestDTO(
            creator_user_id=CREATOR_ID,
            name="Custom Host",
            description="Seats guests.",
            default_scope="branch",
            permission_codes=frozenset({"table.read"}),
        ),
    )

    assert result.name == "Custom Host"
    assert result.is_system is False
    stored_codes = await fixture.role_permission_repo.list_permission_codes_for_role(result.id)
    assert stored_codes == frozenset({"table.read"})


async def test_creating_a_role_publishes_role_created(fixture: _Fixture, session_factory) -> None:
    await _grant_owner(fixture)
    use_case = fixture.use_case(session_factory)

    await use_case.execute(
        TENANT_ID,
        CreateRoleRequestDTO(
            creator_user_id=CREATOR_ID,
            name="Custom Host",
            description=None,
            default_scope="branch",
            permission_codes=frozenset({"table.read"}),
        ),
    )

    assert len(fixture.outbox.published) == 1
    _tenant_id, event = fixture.outbox.published[0]
    assert isinstance(event, RoleCreated)
    assert event.name == "Custom Host"


async def test_cannot_author_a_role_carrying_a_permission_the_creator_lacks(
    fixture: _Fixture, session_factory
) -> None:
    await _grant_owner(fixture)  # holds roles.assign, menu.manage, table.read -- not billing.manage
    use_case = fixture.use_case(session_factory)

    with pytest.raises(InsufficientGrantAuthorityError) as exc_info:
        await use_case.execute(
            TENANT_ID,
            CreateRoleRequestDTO(
                creator_user_id=CREATOR_ID,
                name="Suspicious Role",
                description=None,
                default_scope="branch",
                permission_codes=frozenset({"table.read", "billing.manage"}),
            ),
        )
    assert exc_info.value.reason == "delegation"
    assert await fixture.role_repo.get_by_name(TENANT_ID, "Suspicious Role") is None


async def test_a_caller_holding_no_permissions_at_all_cannot_author_any_role_with_permissions(
    fixture: _Fixture, session_factory
) -> None:
    use_case = fixture.use_case(session_factory)  # CREATOR_ID granted nothing

    with pytest.raises(InsufficientGrantAuthorityError):
        await use_case.execute(
            TENANT_ID,
            CreateRoleRequestDTO(
                creator_user_id=CREATOR_ID,
                name="Empty Handed",
                description=None,
                default_scope="branch",
                permission_codes=frozenset({"table.read"}),
            ),
        )


async def test_authoring_a_role_with_zero_permissions_never_needs_delegation_authority(
    fixture: _Fixture, session_factory
) -> None:
    use_case = fixture.use_case(session_factory)

    result = await use_case.execute(
        TENANT_ID,
        CreateRoleRequestDTO(
            creator_user_id=CREATOR_ID,
            name="Placeholder Role",
            description=None,
            default_scope="branch",
            permission_codes=frozenset(),
        ),
    )
    assert result.name == "Placeholder Role"


async def test_duplicate_role_name_at_the_same_tenant_raises(
    fixture: _Fixture, session_factory
) -> None:
    await _grant_owner(fixture)
    use_case = fixture.use_case(session_factory)

    with pytest.raises(RoleNameConflictError):
        await use_case.execute(
            TENANT_ID,
            CreateRoleRequestDTO(
                creator_user_id=CREATOR_ID,
                name="Tenant Owner",  # already exists, seeded in the fixture
                description=None,
                default_scope="tenant",
                permission_codes=frozenset(),
            ),
        )
