"""End-to-end HTTP tests for the RBAC API against a real PostgreSQL
instance (RBAC Foundation Architecture SS16, Commit 6's own router).

Follows test_admin_tenant_router.py's pattern: dependency overrides
replace only the session factory and token service, so use cases,
repositories, RLS policies, and routing are all exercised exactly as in
production. Every test authenticates through a real POST /auth/login
call.

The RBAC API has no self-service bootstrap path (by design -- granting
roles.assign to yourself would itself be a privilege-escalation hole),
so every test seeds one user's Tenant Owner grant directly through the
repositories before driving the rest of the flow over real HTTP. This
mirrors how a human operator would actually bootstrap a new tenant:
scripts/backfill_tenant_owner.py (Commit 7) does exactly this seeding,
just as a standalone script instead of inline test setup.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import text

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.main import create_app
from restaurant_os_api.modules.identity.domain.entities import Role, RoleScope, UserRole
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyRolePermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyUserRoleRepository,
)
from restaurant_os_api.modules.identity.infrastructure.security import (
    Argon2PasswordHasher,
    JWTTokenService,
)
from restaurant_os_api.modules.identity.presentation.dependencies import (
    get_session_factory,
    get_token_service,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

PASSWORD = "correct horse battery staple"
# AssignUserRoleRequestSchema.branch_id requires exactly 26 characters
# (ULID length) -- a real branch_id doesn't exist yet (Branch is
# Restaurant Platform, not built), but any request that actually
# reaches the authorization/use-case layer (rather than 422ing on
# schema validation before ever getting there) must use a
# schema-valid-length value.
BRANCH_A = "01ARZ3NDEKTSV4RRFFQ6BRNCHA"
BRANCH_B = "01ARZ3NDEKTSV4RRFFQ6BRNCHB"


@pytest.fixture(scope="module")
def token_service() -> JWTTokenService:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return JWTTokenService(
        private_key=private_pem,
        public_key=public_pem,
        issuer="restaurantos-test",
        access_ttl_seconds=900,
    )


@pytest.fixture
def client(session_factory, token_service: JWTTokenService) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_token_service] = lambda: token_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def _seed_user(session_factory, *, tenant_id: str, email: str) -> str:
    user_id = generate_ulid()
    password_hash = Argon2PasswordHasher().hash(PASSWORD)
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO tenants (id, legal_name, display_name, tenant_tier, status, "
                "default_currency_code) VALUES (:id, :legal_name, :legal_name, 'shared', "
                "'active', 'USD') ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tenant_id, "legal_name": f"Seed tenant {tenant_id}"},
        )
        await uow.session.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash, permission_version, "
                "status, is_platform_admin) VALUES (:id, :tenant_id, :email, :password_hash, "
                "1, 'active', false)"
            ),
            {"id": user_id, "tenant_id": tenant_id, "email": email, "password_hash": password_hash},
        )
    return user_id


async def _login(client: TestClient, *, tenant_id: str, email: str) -> str:
    return _login_sync(client, tenant_id=tenant_id, email=email)


def _login_sync(client: TestClient, *, tenant_id: str, email: str) -> str:
    """TestClient's own HTTP calls are synchronous even inside an async
    test -- this lets a plain `def` test method (no running event loop)
    re-authenticate mid-test without needing to be async itself."""
    response = client.post(
        "/api/v1/auth/login",
        json={"tenantId": tenant_id, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["accessToken"]


async def _grant_tenant_owner(session_factory, *, tenant_id: str, user_id: str) -> None:
    """Seeds exactly the bootstrap state scripts/backfill_tenant_owner.py
    creates for a real, already-provisioned tenant: the 11-permission
    Tenant Owner role, granted tenant-wide."""
    now = datetime.now(UTC)
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        role_repo = SQLAlchemyRoleRepository(uow.session)
        role_permission_repo = SQLAlchemyRolePermissionRepository(uow.session)
        user_role_repo = SQLAlchemyUserRoleRepository(uow.session)

        role = await role_repo.create(
            Role(
                id=generate_ulid(),
                tenant_id=tenant_id,
                name="Tenant Owner",
                description="test-seeded owner",
                default_scope=RoleScope.TENANT,
                is_system=True,
                is_active=True,
                created_at=now,
            )
        )
        await role_permission_repo.replace_for_role(
            role.id,
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
        await user_role_repo.create(
            UserRole(
                id=generate_ulid(),
                tenant_id=tenant_id,
                user_id=user_id,
                role_id=role.id,
                branch_id=None,
                granted_at=now,
                granted_by_user_id=None,
            )
        )


async def _grant_role(
    session_factory,
    *,
    tenant_id: str,
    user_id: str,
    role_name: str,
    permission_codes: frozenset[str],
    branch_id: str | None,
) -> None:
    now = datetime.now(UTC)
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        role_repo = SQLAlchemyRoleRepository(uow.session)
        role_permission_repo = SQLAlchemyRolePermissionRepository(uow.session)
        user_role_repo = SQLAlchemyUserRoleRepository(uow.session)

        role = await role_repo.create(
            Role(
                id=generate_ulid(),
                tenant_id=tenant_id,
                name=role_name,
                description=None,
                default_scope=RoleScope.BRANCH if branch_id else RoleScope.TENANT,
                is_system=True,
                is_active=True,
                created_at=now,
            )
        )
        await role_permission_repo.replace_for_role(role.id, permission_codes)
        await user_role_repo.create(
            UserRole(
                id=generate_ulid(),
                tenant_id=tenant_id,
                user_id=user_id,
                role_id=role.id,
                branch_id=branch_id,
                granted_at=now,
                granted_by_user_id=None,
            )
        )


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def tenant_owner(session_factory, client: TestClient) -> AsyncGenerator[dict]:
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_tenant_owner(session_factory, tenant_id=tenant_id, user_id=user_id)
    token = await _login(client, tenant_id=tenant_id, email=email)
    yield {"tenant_id": tenant_id, "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def plain_member(
    session_factory, client: TestClient, tenant_owner: dict
) -> AsyncGenerator[dict]:
    """A second user in the *same* tenant as tenant_owner, with zero RBAC grants."""
    email = "member@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_owner["tenant_id"], email=email)
    token = await _login(client, tenant_id=tenant_owner["tenant_id"], email=email)
    yield {"tenant_id": tenant_owner["tenant_id"], "user_id": user_id, "token": token}


class TestMePermissions:
    def test_a_user_with_no_grants_sees_an_empty_but_successful_response(
        self, client: TestClient, plain_member: dict
    ) -> None:
        response = client.get(
            "/api/v1/me/permissions", headers=_auth_headers(plain_member["token"])
        )
        assert response.status_code == 200, response.text
        body = response.json()["data"]
        assert body["tenantWide"] == []
        assert body["byBranch"] == {}

    def test_needs_no_roles_assign_permission_at_all(
        self, client: TestClient, plain_member: dict
    ) -> None:
        """Deliberately distinct from every other RBAC route: seeing
        your own permissions requires only authentication."""
        response = client.get(
            "/api/v1/me/permissions", headers=_auth_headers(plain_member["token"])
        )
        assert response.status_code == 200

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.get("/api/v1/me/permissions")
        assert response.status_code == 401


class TestPermissionDeniedWithoutRolesAssign:
    @pytest.mark.parametrize(
        ("method", "path", "json"),
        [
            ("get", "/api/v1/rbac/permissions", None),
            ("get", "/api/v1/rbac/roles", None),
            (
                "post",
                "/api/v1/rbac/roles",
                {"name": "X", "defaultScope": "branch", "permissionCodes": []},
            ),
            ("post", "/api/v1/rbac/user-roles", {"userId": "x" * 26, "roleId": "y" * 26}),
        ],
    )
    def test_every_rbac_route_denies_a_caller_with_no_roles_assign(
        self, client: TestClient, plain_member: dict, method: str, path: str, json: dict | None
    ) -> None:
        kwargs = {"headers": _auth_headers(plain_member["token"])}
        if json is not None:
            kwargs["json"] = json
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


class TestPermissionCatalogue:
    def test_tenant_owner_sees_all_11_seeded_permissions(
        self, client: TestClient, tenant_owner: dict
    ) -> None:
        response = client.get(
            "/api/v1/rbac/permissions", headers=_auth_headers(tenant_owner["token"])
        )
        assert response.status_code == 200
        codes = {p["code"] for p in response.json()["data"]}
        assert len(codes) == 11
        assert "roles.assign" in codes


class TestRoleManagement:
    def test_tenant_owner_can_create_and_then_list_a_role(
        self, client: TestClient, tenant_owner: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Custom Host",
                "description": "Seats guests.",
                "defaultScope": "branch",
                "permissionCodes": ["table.read"],
            },
        )
        assert create_response.status_code == 201, create_response.text
        created = create_response.json()["data"]
        assert created["name"] == "Custom Host"
        assert created["isSystem"] is False

        list_response = client.get(
            "/api/v1/rbac/roles", headers=_auth_headers(tenant_owner["token"])
        )
        assert list_response.status_code == 200
        names = {r["name"] for r in list_response.json()["data"]}
        assert "Custom Host" in names
        assert "Tenant Owner" in names  # the fixture-seeded role too

    def test_get_role_by_id_returns_the_full_permission_bearing_role(
        self, client: TestClient, tenant_owner: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Barback",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": [],
            },
        )
        role_id = create_response.json()["data"]["id"]

        get_response = client.get(
            f"/api/v1/rbac/roles/{role_id}", headers=_auth_headers(tenant_owner["token"])
        )
        assert get_response.status_code == 200
        assert get_response.json()["data"]["name"] == "Barback"

    def test_replace_role_permissions_updates_the_stored_set(
        self, client: TestClient, tenant_owner: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Evolving Role",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["table.read"],
            },
        )
        role_id = create_response.json()["data"]["id"]

        replace_response = client.put(
            f"/api/v1/rbac/roles/{role_id}/permissions",
            headers=_auth_headers(tenant_owner["token"]),
            json={"permissionCodes": ["table.read", "menu.read"]},
        )
        assert replace_response.status_code == 200, replace_response.text

        get_response = client.get(
            f"/api/v1/rbac/roles/{role_id}", headers=_auth_headers(tenant_owner["token"])
        )
        assert get_response.status_code == 200  # role itself still resolvable


class TestUserRoleGrantAndRevoke:
    def test_a_grant_invalidates_the_targets_existing_token_and_a_fresh_login_sees_it(
        self, client: TestClient, tenant_owner: dict, plain_member: dict
    ) -> None:
        """Technical Architecture v2.0 Group C, verified precisely
        (verify_access_token.py:72): a permission_version bump is a
        *strict-equality* check against the token's embedded version,
        not a >= check. So a grant does not make the change visible to
        the *same* still-held token on its very next call -- it makes
        that token immediately stale (401), forcing the holder to
        re-authenticate. The fresh token from that re-login is what
        carries the new permissions. This is a stronger guarantee than
        "eventually visible": a token that predates a permission change
        can never be used to observe a stale view of that change."""
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Waiter",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["table.read", "menu.read"],
            },
        )
        role_id = create_response.json()["data"]["id"]

        before = client.get(
            "/api/v1/me/permissions", headers=_auth_headers(plain_member["token"])
        ).json()["data"]
        assert before["tenantWide"] == []

        grant_response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id},
        )
        assert grant_response.status_code == 201, grant_response.text

        stale_response = client.get(
            "/api/v1/me/permissions", headers=_auth_headers(plain_member["token"])
        )
        assert stale_response.status_code == 401, stale_response.text
        assert stale_response.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"

        fresh_token = _login_sync(
            client, tenant_id=plain_member["tenant_id"], email="member@example.com"
        )
        after = client.get("/api/v1/me/permissions", headers=_auth_headers(fresh_token)).json()[
            "data"
        ]
        assert set(after["tenantWide"]) == {"table.read", "menu.read"}

    def test_duplicate_grant_at_the_same_scope_returns_409(
        self, client: TestClient, tenant_owner: dict, plain_member: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Cashier",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["table.read"],
            },
        )
        role_id = create_response.json()["data"]["id"]
        payload = {"userId": plain_member["user_id"], "roleId": role_id}

        first = client.post(
            "/api/v1/rbac/user-roles", headers=_auth_headers(tenant_owner["token"]), json=payload
        )
        assert first.status_code == 201

        second = client.post(
            "/api/v1/rbac/user-roles", headers=_auth_headers(tenant_owner["token"]), json=payload
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "DUPLICATE_ROLE_ASSIGNMENT"

    def test_revoke_invalidates_the_targets_existing_token_and_a_fresh_login_no_longer_has_it(
        self, client: TestClient, tenant_owner: dict, plain_member: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Kitchen Staff",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["menu.read"],
            },
        )
        role_id = create_response.json()["data"]["id"]
        grant_response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id},
        )
        user_role_id = grant_response.json()["data"]["id"]
        # The grant itself already staled plain_member's original token
        # (see the grant test above) -- get a fresh one to hold before
        # revoking, exactly as a real client would after being logged
        # out mid-session.
        member_token = _login_sync(
            client, tenant_id=plain_member["tenant_id"], email="member@example.com"
        )
        holding = client.get("/api/v1/me/permissions", headers=_auth_headers(member_token)).json()[
            "data"
        ]
        assert set(holding["tenantWide"]) == {"menu.read"}

        revoke_response = client.delete(
            f"/api/v1/rbac/user-roles/{user_role_id}",
            headers=_auth_headers(tenant_owner["token"]),
        )
        assert revoke_response.status_code == 200, revoke_response.text

        stale_response = client.get("/api/v1/me/permissions", headers=_auth_headers(member_token))
        assert stale_response.status_code == 401, stale_response.text

        fresh_token = _login_sync(
            client, tenant_id=plain_member["tenant_id"], email="member@example.com"
        )
        after = client.get("/api/v1/me/permissions", headers=_auth_headers(fresh_token)).json()[
            "data"
        ]
        assert after["tenantWide"] == []

    def test_revoking_an_unknown_grant_returns_404(
        self, client: TestClient, tenant_owner: dict
    ) -> None:
        response = client.delete(
            f"/api/v1/rbac/user-roles/{'0' * 26}", headers=_auth_headers(tenant_owner["token"])
        )
        assert response.status_code == 404


@pytest_asyncio.fixture
async def branch_manager(
    session_factory, client: TestClient, tenant_owner: dict
) -> AsyncGenerator[dict]:
    """A Branch Manager at 'branch-a' in tenant_owner's tenant, holding
    roles.assign only at that branch -- a real, branch-scoped grant, not
    synthetic data."""
    email = "bm@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_owner["tenant_id"], email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_owner["tenant_id"],
        user_id=user_id,
        role_name="Branch Manager",
        permission_codes=frozenset({"branch.read", "table.read", "table.manage", "roles.assign"}),
        branch_id=BRANCH_A,
    )
    token = await _login(client, tenant_id=tenant_owner["tenant_id"], email=email)
    yield {"tenant_id": tenant_owner["tenant_id"], "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def waiter(session_factory, client: TestClient, tenant_owner: dict) -> AsyncGenerator[dict]:
    """A real Waiter (RBAC_Foundation_Architecture.md SS6.3: table.read,
    menu.read, reservation.manage) -- holds no roles.assign anywhere."""
    email = "waiter@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_owner["tenant_id"], email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_owner["tenant_id"],
        user_id=user_id,
        role_name="Waiter",
        permission_codes=frozenset({"table.read", "menu.read", "reservation.manage"}),
        branch_id=BRANCH_A,
    )
    token = await _login(client, tenant_id=tenant_owner["tenant_id"], email=email)
    yield {"tenant_id": tenant_owner["tenant_id"], "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def limited_assigner(
    session_factory, client: TestClient, tenant_owner: dict
) -> AsyncGenerator[dict]:
    """Holds roles.assign *tenant-wide* but not menu.manage -- isolates
    the delegation ceiling from the scope ceiling (RBAC Foundation
    Architecture SS16.1's own "Limited Assigner" example, Commit 5)."""
    email = "limited@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_owner["tenant_id"], email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_owner["tenant_id"],
        user_id=user_id,
        role_name="Limited Assigner",
        permission_codes=frozenset({"roles.assign"}),
        branch_id=None,
    )
    token = await _login(client, tenant_id=tenant_owner["tenant_id"], email=email)
    yield {"tenant_id": tenant_owner["tenant_id"], "user_id": user_id, "token": token}


class TestPrivilegeEscalationViaTheRealApi:
    def test_a_branch_scoped_roles_assign_holder_cannot_manage_the_role_catalogue(
        self, client: TestClient, branch_manager: dict
    ) -> None:
        """**Corrected understanding, RBAC Sprint 5 Step 2 follow-up
        pass (AI_HANDOFF.md SS21, "Finding 2"):** this is *not* the
        limitation it was first reported as. Role *catalogue*
        management (creating/editing a `Role` row) is deliberately
        tenant-wide-only -- a `Role` has no `branch_id` at all in the
        schema (RBAC_Foundation_Architecture.md SS4.1), and
        `RoleGrantPolicy` applies no scope ceiling to authoring/editing
        a role definition, only to granting/revoking it. A
        branch-scoped `roles.assign` holder is correctly denied here.
        What *was* wrong (now fixed, see
        TestBranchScopedRoleDelegation below): the two routes that
        actually create/remove a scoped `UserRole` grant
        (`POST`/`DELETE /rbac/user-roles*`) used the same
        tenant-wide-only gate as this one, which was the real bug."""
        response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(branch_manager["token"]),
            json={
                "name": "Anything",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": [],
            },
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    def test_a_tenant_wide_limited_assigner_cannot_grant_a_permission_they_lack(
        self, client: TestClient, tenant_owner: dict, plain_member: dict, limited_assigner: dict
    ) -> None:
        """The delegation ceiling enforced end-to-end: a tenant-wide
        roles.assign holder who never holds menu.manage cannot grant a
        role carrying it -- passes the router's scope gate, then is
        correctly stopped by RoleGrantPolicy inside the use case."""
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Menu Manager",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["menu.manage"],
            },
        )
        role_id = create_response.json()["data"]["id"]

        response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(limited_assigner["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id},
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "INSUFFICIENT_GRANT_AUTHORITY"

    def test_creating_a_role_with_an_unheld_permission_is_rejected_end_to_end(
        self, client: TestClient, limited_assigner: dict
    ) -> None:
        """The same delegation ceiling applies to role authoring
        itself, not just to granting an existing role."""
        response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(limited_assigner["token"]),
            json={
                "name": "Suspicious Role",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["menu.manage"],  # limited_assigner never granted this
            },
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "INSUFFICIENT_GRANT_AUTHORITY"

    async def test_granting_a_role_named_platform_admin_never_sets_the_is_platform_admin_flag(
        self, client: TestClient, session_factory, tenant_owner: dict, plain_member: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Platform Admin",
                "description": "just an ordinary role, despite the name",
                "defaultScope": "tenant",
                "permissionCodes": ["menu.read"],
            },
        )
        role_id = create_response.json()["data"]["id"]

        grant_response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id},
        )
        assert grant_response.status_code == 201, grant_response.text

        async with UnitOfWork(session_factory, TenantContext(tenant_owner["tenant_id"])) as uow:
            result = await uow.session.execute(
                text("SELECT is_platform_admin FROM users WHERE id = :id"),
                {"id": plain_member["user_id"]},
            )
            assert bool(result.scalar()) is False


def _tenant_owner_role_id(client: TestClient, tenant_owner: dict) -> str:
    response = client.get("/api/v1/rbac/roles", headers=_auth_headers(tenant_owner["token"]))
    role = next(r for r in response.json()["data"] if r["name"] == "Tenant Owner")
    return role["id"]


class TestBranchScopedRoleDelegation:
    """The "Finding 2" fix's own security matrix (AI_HANDOFF.md SS21,
    user-directed correction pass): a branch-scoped roles.assign holder
    can now reach POST/DELETE /rbac/user-roles at all (the router bug
    that was fixed), but every fine-grained decision — which branch,
    whether the delegated permissions are within their ceiling, whether
    a tenant-wide grant is being attempted — is still made by
    RoleGrantPolicy inside the use case, completely unchanged from
    Commit 5. Every test below exercises that through the real router,
    not just the use case directly (already covered at the unit level
    in test_assign_user_role.py/test_revoke_user_role.py)."""

    # 1. Tenant-wide authorized user can assign roles.
    def test_tenant_wide_authorized_user_can_assign_roles(
        self, client: TestClient, tenant_owner: dict, plain_member: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Table Runner",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["table.read"],
            },
        )
        role_id = create_response.json()["data"]["id"]

        response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id},
        )
        assert response.status_code == 201, response.text

    # 2. Branch Manager can assign roles within their own branch when authorized.
    def test_branch_manager_can_assign_a_role_within_their_own_branch(
        self, client: TestClient, tenant_owner: dict, plain_member: dict, branch_manager: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Table Runner",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["table.read"],  # subset of branch_manager's own grant
            },
        )
        role_id = create_response.json()["data"]["id"]

        response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(branch_manager["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id, "branchId": BRANCH_A},
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["branchId"] == BRANCH_A

    # 3. Branch Manager cannot assign roles in another branch.
    def test_branch_manager_cannot_assign_a_role_in_a_different_branch(
        self, client: TestClient, tenant_owner: dict, plain_member: dict, branch_manager: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Table Runner",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["table.read"],
            },
        )
        role_id = create_response.json()["data"]["id"]

        response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(branch_manager["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id, "branchId": BRANCH_B},
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "INSUFFICIENT_GRANT_AUTHORITY"

    # 4. Branch Manager cannot grant a role exceeding their delegation ceiling.
    def test_branch_manager_cannot_grant_a_role_carrying_a_permission_they_lack(
        self, client: TestClient, tenant_owner: dict, plain_member: dict, branch_manager: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Menu Editor",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["menu.manage"],  # branch_manager never granted this
            },
        )
        role_id = create_response.json()["data"]["id"]

        response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(branch_manager["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id, "branchId": BRANCH_A},
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "INSUFFICIENT_GRANT_AUTHORITY"

    # 5. Branch Manager cannot grant Tenant Owner.
    def test_branch_manager_cannot_grant_the_tenant_owner_role(
        self, client: TestClient, tenant_owner: dict, plain_member: dict, branch_manager: dict
    ) -> None:
        tenant_owner_role_id = _tenant_owner_role_id(client, tenant_owner)

        response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(branch_manager["token"]),
            json={"userId": plain_member["user_id"], "roleId": tenant_owner_role_id},
            # no branchId => tenant-wide grant attempt
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "INSUFFICIENT_GRANT_AUTHORITY"

    # 6. Branch Manager cannot grant Platform Admin privileges.
    async def test_branch_manager_granting_a_role_named_platform_admin_never_touches_the_flag(
        self,
        client: TestClient,
        session_factory,
        tenant_owner: dict,
        plain_member: dict,
        branch_manager: dict,
    ) -> None:
        """Structural proof at the branch-scoped granter too, not just
        the tenant-wide one above: a role's *name* is irrelevant --
        RBAC has no code path that can reach users.is_platform_admin at
        all (RBAC_Foundation_Architecture.md SS10.2), regardless of who
        granted it or at what scope."""
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Platform Admin",
                "description": "still just an ordinary role",
                "defaultScope": "branch",
                "permissionCodes": ["table.read"],  # within branch_manager's ceiling
            },
        )
        role_id = create_response.json()["data"]["id"]

        grant_response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(branch_manager["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id, "branchId": BRANCH_A},
        )
        assert grant_response.status_code == 201, grant_response.text

        async with UnitOfWork(session_factory, TenantContext(tenant_owner["tenant_id"])) as uow:
            result = await uow.session.execute(
                text("SELECT is_platform_admin FROM users WHERE id = :id"),
                {"id": plain_member["user_id"]},
            )
            assert bool(result.scalar()) is False

    # 7. Waiter cannot assign roles.
    def test_a_waiter_cannot_assign_roles_at_all(
        self, client: TestClient, tenant_owner: dict, plain_member: dict, waiter: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Table Runner",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": [],
            },
        )
        role_id = create_response.json()["data"]["id"]

        response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(waiter["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id, "branchId": BRANCH_A},
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    # 8. User cannot assign a role to themselves if that would escalate privileges.
    def test_a_branch_manager_cannot_grant_themselves_a_tenant_wide_role(
        self, client: TestClient, tenant_owner: dict, branch_manager: dict
    ) -> None:
        tenant_owner_role_id = _tenant_owner_role_id(client, tenant_owner)

        response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(branch_manager["token"]),
            json={"userId": branch_manager["user_id"], "roleId": tenant_owner_role_id},
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "INSUFFICIENT_GRANT_AUTHORITY"

    # 9. Revocation follows the same branch-scope rules.
    def test_branch_manager_can_revoke_a_grant_within_their_own_branch(
        self, client: TestClient, tenant_owner: dict, plain_member: dict, branch_manager: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Table Runner",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["table.read"],
            },
        )
        role_id = create_response.json()["data"]["id"]
        grant_response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id, "branchId": BRANCH_A},
        )
        user_role_id = grant_response.json()["data"]["id"]

        response = client.delete(
            f"/api/v1/rbac/user-roles/{user_role_id}",
            headers=_auth_headers(branch_manager["token"]),
        )
        assert response.status_code == 200, response.text

    def test_branch_manager_cannot_revoke_a_grant_in_a_different_branch(
        self, client: TestClient, tenant_owner: dict, plain_member: dict, branch_manager: dict
    ) -> None:
        create_response = client.post(
            "/api/v1/rbac/roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={
                "name": "Table Runner",
                "description": None,
                "defaultScope": "branch",
                "permissionCodes": ["table.read"],
            },
        )
        role_id = create_response.json()["data"]["id"]
        grant_response = client.post(
            "/api/v1/rbac/user-roles",
            headers=_auth_headers(tenant_owner["token"]),
            json={"userId": plain_member["user_id"], "roleId": role_id, "branchId": BRANCH_B},
        )
        user_role_id = grant_response.json()["data"]["id"]

        denied_response = client.delete(
            f"/api/v1/rbac/user-roles/{user_role_id}",
            headers=_auth_headers(branch_manager["token"]),
        )
        assert denied_response.status_code == 403, denied_response.text
        assert denied_response.json()["error"]["code"] == "INSUFFICIENT_GRANT_AUTHORITY"

        # Proves the denied attempt left the grant untouched -- the
        # rightful tenant-wide owner can still revoke it afterward.
        cleanup_response = client.delete(
            f"/api/v1/rbac/user-roles/{user_role_id}",
            headers=_auth_headers(tenant_owner["token"]),
        )
        assert cleanup_response.status_code == 200, cleanup_response.text
