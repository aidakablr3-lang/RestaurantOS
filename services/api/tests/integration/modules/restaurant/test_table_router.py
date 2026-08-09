"""End-to-end HTTP tests for Table CRUD + status-change against a real
PostgreSQL instance (Sprint 5 Step 4.5).

Follows test_table_zone_router.py's exact pattern. CRUD routes are
nested under branch_id, gated by table.manage/table.read via
require_branch_permission. The status-change route
(POST /api/v1/tables/{id}/status) is architecture's own deliberately
flat path -- gated by the coarser require_permission_at_any_scope
plus ChangeTableStatusUseCase's own resolve_and_authorize_branch call;
see table_router.py's docstring.
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


def _login_sync(client: TestClient, *, tenant_id: str, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"tenantId": tenant_id, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["accessToken"]


async def _grant_role(
    session_factory,
    *,
    tenant_id: str,
    user_id: str,
    permission_codes: frozenset[str],
    branch_id: str | None = None,
    is_active: bool = True,
) -> str:
    """Returns the created UserRole's id so a test can revoke it."""
    now = datetime.now(UTC)
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        role_repo = SQLAlchemyRoleRepository(uow.session)
        role_permission_repo = SQLAlchemyRolePermissionRepository(uow.session)
        user_role_repo = SQLAlchemyUserRoleRepository(uow.session)

        role = await role_repo.create(
            Role(
                id=generate_ulid(),
                tenant_id=tenant_id,
                name=f"Role {generate_ulid()}",
                description=None,
                default_scope=RoleScope.BRANCH if branch_id else RoleScope.TENANT,
                is_system=False,
                is_active=is_active,
                created_at=now,
            )
        )
        await role_permission_repo.replace_for_role(role.id, permission_codes)
        user_role = await user_role_repo.create(
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
    return user_role.id


async def _revoke_role(session_factory, *, tenant_id: str, user_role_id: str) -> None:
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await SQLAlchemyUserRoleRepository(uow.session).revoke(tenant_id, user_role_id)


async def _create_restaurant(session_factory, tenant_id: str, *, name: str = "R") -> str:
    restaurant_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO restaurants (id, tenant_id, legal_name, display_name, "
                "default_currency_code) VALUES (:id, :tenant_id, :name, :name, 'USD')"
            ),
            {"id": restaurant_id, "tenant_id": tenant_id, "name": name},
        )
    return restaurant_id


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def owner(session_factory, client: TestClient) -> AsyncGenerator[dict]:
    """A user holding table.read/table.manage/branch.manage tenant-wide."""
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        permission_codes=frozenset(
            {"table.read", "table.manage", "branch.manage", "restaurant.read"}
        ),
    )
    token = _login_sync(client, tenant_id=tenant_id, email=email)
    yield {"tenant_id": tenant_id, "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def restaurant_id(session_factory, owner: dict) -> str:
    return await _create_restaurant(session_factory, owner["tenant_id"])


@pytest_asyncio.fixture
async def branch(client: TestClient, owner: dict, restaurant_id: str) -> dict:
    response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches",
        headers=_auth_headers(owner["token"]),
        json={"name": "Downtown"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest_asyncio.fixture
async def table_zone(client: TestClient, owner: dict, branch: dict) -> dict:
    response = client.post(
        f"/api/v1/branches/{branch['id']}/table-zones",
        headers=_auth_headers(owner["token"]),
        json={"name": "Patio"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest_asyncio.fixture
async def reader_only(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    email = "reader@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    await _grant_role(
        session_factory,
        tenant_id=owner["tenant_id"],
        user_id=user_id,
        permission_codes=frozenset({"table.read"}),
    )
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def no_permission(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    email = "noperm@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


def _create_body(table_zone_id: str, **overrides) -> dict:
    body = {"tableZoneId": table_zone_id, "tableNumber": "12A", "capacity": 4}
    body.update(overrides)
    return body


def _create_table(
    client: TestClient, owner: dict, branch_id: str, table_zone_id: str, **overrides
) -> dict:
    response = client.post(
        f"/api/v1/branches/{branch_id}/tables",
        headers=_auth_headers(owner["token"]),
        json=_create_body(table_zone_id, **overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestCreateTable:
    def test_a_manage_holder_can_create_a_table(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json=_create_body(table_zone["id"]),
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["tableNumber"] == "12A"
        assert data["capacity"] == 4
        assert data["status"] == "available"
        assert data["branchId"] == branch["id"]
        assert data["tableZoneId"] == table_zone["id"]
        assert data["tenantId"] == owner["tenant_id"]

    def test_an_unknown_branch_id_is_404(
        self, client: TestClient, owner: dict, table_zone: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{'0' * 26}/tables",
            headers=_auth_headers(owner["token"]),
            json=_create_body(table_zone["id"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_an_unknown_table_zone_id_is_404(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json=_create_body("0" * 26),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_ZONE_NOT_FOUND"

    async def test_a_table_zone_belonging_to_a_different_branch_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict, table_zone: dict
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]

        response = client.post(
            f"/api/v1/branches/{other_branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json=_create_body(table_zone["id"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_ZONE_NOT_FOUND"

    async def test_a_branch_belonging_to_another_tenant_is_404_not_a_leak(
        self, client: TestClient, owner: dict, table_zone: dict, session_factory
    ) -> None:
        other_tenant_id = generate_ulid()
        other_email = "other@example.com"
        other_user_id = await _seed_user(
            session_factory, tenant_id=other_tenant_id, email=other_email
        )
        await _grant_role(
            session_factory,
            tenant_id=other_tenant_id,
            user_id=other_user_id,
            permission_codes=frozenset({"restaurant.manage", "branch.manage"}),
        )
        other_token = _login_sync(client, tenant_id=other_tenant_id, email=other_email)
        other_restaurant = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(other_token),
            json={"legalName": "Other", "displayName": "Other", "defaultCurrencyCode": "USD"},
        ).json()["data"]
        other_branch = client.post(
            f"/api/v1/restaurants/{other_restaurant['id']}/branches",
            headers=_auth_headers(other_token),
            json={"name": "Other Branch"},
        ).json()["data"]

        response = client.post(
            f"/api/v1/branches/{other_branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json=_create_body(table_zone["id"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_a_duplicate_table_number_under_the_same_branch_is_a_conflict(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        _create_table(client, owner, branch["id"], table_zone["id"], tableNumber="7")

        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json=_create_body(table_zone["id"], tableNumber="7"),
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "TABLE_NUMBER_ALREADY_EXISTS"

    def test_requires_authentication(
        self, client: TestClient, branch: dict, table_zone: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables", json=_create_body(table_zone["id"])
        )
        assert response.status_code == 401

    def test_denied_without_table_manage(
        self, client: TestClient, reader_only: dict, branch: dict, table_zone: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(reader_only["token"]),
            json=_create_body(table_zone["id"]),
        )
        assert response.status_code == 403

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, branch: dict, table_zone: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(no_permission["token"]),
            json=_create_body(table_zone["id"]),
        )
        assert response.status_code == 403

    async def test_denied_when_the_only_grant_is_on_an_inactive_role(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict, session_factory
    ) -> None:
        email = "inactive@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
            is_active=False,
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(token),
            json=_create_body(table_zone["id"]),
        )
        assert response.status_code == 403

    async def test_a_branch_scoped_manage_grant_can_create_in_its_own_branch(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict, session_factory
    ) -> None:
        email = "branchmgr@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(token),
            json=_create_body(table_zone["id"]),
        )
        assert response.status_code == 201, response.text

    async def test_a_branch_scoped_manage_grant_cannot_create_in_a_different_branch(
        self,
        client: TestClient,
        owner: dict,
        restaurant_id: str,
        branch: dict,
        table_zone: dict,
        session_factory,
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]

        email = "scoped@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/branches/{other_branch['id']}/tables",
            headers=_auth_headers(token),
            json=_create_body(table_zone["id"]),
        )
        assert response.status_code == 403

    def test_capacity_zero_is_rejected(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json=_create_body(table_zone["id"], capacity=0),
        )
        assert response.status_code == 422

    def test_negative_capacity_is_rejected(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json=_create_body(table_zone["id"], capacity=-1),
        )
        assert response.status_code == 422

    def test_missing_required_field_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json={},
        )
        assert response.status_code == 422


class TestCreateTableIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/tables"
        body = _create_body(table_zone["id"])

        first = client.post(url, headers=headers, json=body)
        second = client.post(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()

        list_response = client.get(url, headers=_auth_headers(owner["token"]))
        assert list_response.json()["meta"]["total"] == 1

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/tables"

        first = client.post(
            url, headers=headers, json=_create_body(table_zone["id"], tableNumber="1")
        )
        assert first.status_code == 201, first.text

        second = client.post(
            url, headers=headers, json=_create_body(table_zone["id"], tableNumber="2")
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestGetTable:
    def test_a_read_holder_can_get_a_table(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        response = client.get(
            f"/api/v1/branches/{branch['id']}/tables/{table['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] == table["id"]

    def test_unknown_id_returns_404(self, client: TestClient, owner: dict, branch: dict) -> None:
        response = client.get(
            f"/api/v1/branches/{branch['id']}/tables/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    async def test_a_table_belonging_to_a_different_branch_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict, table_zone: dict
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        other_zone = client.post(
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json={"name": "Bar"},
        ).json()["data"]
        other_table = _create_table(client, owner, other_branch["id"], other_zone["id"])

        response = client.get(
            f"/api/v1/branches/{branch['id']}/tables/{other_table['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    async def test_a_table_in_another_tenant_is_a_404_not_a_403(
        self, client: TestClient, owner: dict, branch: dict, session_factory
    ) -> None:
        other_tenant_id = generate_ulid()
        other_email = "other@example.com"
        other_user_id = await _seed_user(
            session_factory, tenant_id=other_tenant_id, email=other_email
        )
        await _grant_role(
            session_factory,
            tenant_id=other_tenant_id,
            user_id=other_user_id,
            permission_codes=frozenset({"restaurant.manage", "branch.manage", "table.manage"}),
        )
        other_token = _login_sync(client, tenant_id=other_tenant_id, email=other_email)
        other_restaurant = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(other_token),
            json={"legalName": "Other", "displayName": "Other", "defaultCurrencyCode": "USD"},
        ).json()["data"]
        other_branch = client.post(
            f"/api/v1/restaurants/{other_restaurant['id']}/branches",
            headers=_auth_headers(other_token),
            json={"name": "Other Branch"},
        ).json()["data"]
        other_zone = client.post(
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(other_token),
            json={"name": "Zone"},
        ).json()["data"]
        other_table = client.post(
            f"/api/v1/branches/{other_branch['id']}/tables",
            headers=_auth_headers(other_token),
            json=_create_body(other_zone["id"]),
        ).json()["data"]

        response = client.get(
            f"/api/v1/branches/{branch['id']}/tables/{other_table['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    async def test_branch_scoped_grant_can_read_its_own_branchs_table(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict, session_factory
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        email = "branchreader@example.com"

        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.get(
            f"/api/v1/branches/{branch['id']}/tables/{table['id']}",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text

    def test_requires_authentication(self, client: TestClient, branch: dict) -> None:
        response = client.get(f"/api/v1/branches/{branch['id']}/tables/{'0' * 26}")
        assert response.status_code == 401


class TestListTables:
    def test_lists_only_the_requested_branchs_tables(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        for number in ("A", "B", "C"):
            _create_table(client, owner, branch["id"], table_zone["id"], tableNumber=number)

        response = client.get(
            f"/api/v1/branches/{branch['id']}/tables", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 3

    def test_ordered_deterministically_by_table_number(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        _create_table(client, owner, branch["id"], table_zone["id"], tableNumber="3")
        _create_table(client, owner, branch["id"], table_zone["id"], tableNumber="1")
        _create_table(client, owner, branch["id"], table_zone["id"], tableNumber="2")

        response = client.get(
            f"/api/v1/branches/{branch['id']}/tables", headers=_auth_headers(owner["token"])
        )
        assert [t["tableNumber"] for t in response.json()["data"]] == ["1", "2", "3"]

    def test_pagination_offset_and_limit(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        for i in range(5):
            _create_table(client, owner, branch["id"], table_zone["id"], tableNumber=f"{i}")

        page_1 = client.get(
            f"/api/v1/branches/{branch['id']}/tables?offset=0&limit=2",
            headers=_auth_headers(owner["token"]),
        )
        page_2 = client.get(
            f"/api/v1/branches/{branch['id']}/tables?offset=2&limit=2",
            headers=_auth_headers(owner["token"]),
        )
        assert len(page_1.json()["data"]) == 2
        assert len(page_2.json()["data"]) == 2
        assert page_1.json()["meta"]["total"] == 5
        ids_1 = {t["id"] for t in page_1.json()["data"]}
        ids_2 = {t["id"] for t in page_2.json()["data"]}
        assert ids_1.isdisjoint(ids_2)

    def test_an_unknown_branch_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(
            f"/api/v1/branches/{'0' * 26}/tables", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, branch: dict) -> None:
        response = client.get(f"/api/v1/branches/{branch['id']}/tables")
        assert response.status_code == 401

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, branch: dict
    ) -> None:
        response = client.get(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(no_permission["token"]),
        )
        assert response.status_code == 403


class TestUpdateTable:
    def test_a_manage_holder_can_update_number_and_capacity(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])

        response = client.patch(
            f"/api/v1/branches/{branch['id']}/tables/{table['id']}",
            headers=_auth_headers(owner["token"]),
            json={"tableZoneId": table_zone["id"], "tableNumber": "Renamed", "capacity": 8},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["tableNumber"] == "Renamed"
        assert data["capacity"] == 8
        assert data["id"] == table["id"]
        assert data["status"] == "available"

    async def test_can_move_a_table_to_a_different_zone_within_the_same_branch(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        other_zone = client.post(
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json={"name": "Bar"},
        ).json()["data"]
        table = _create_table(client, owner, branch["id"], table_zone["id"])

        response = client.patch(
            f"/api/v1/branches/{branch['id']}/tables/{table['id']}",
            headers=_auth_headers(owner["token"]),
            json={"tableZoneId": other_zone["id"], "tableNumber": "12A", "capacity": 4},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["tableZoneId"] == other_zone["id"]

    async def test_moving_to_a_zone_in_a_different_branch_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict, table_zone: dict
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        other_zone = client.post(
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json={"name": "Bar"},
        ).json()["data"]
        table = _create_table(client, owner, branch["id"], table_zone["id"])

        response = client.patch(
            f"/api/v1/branches/{branch['id']}/tables/{table['id']}",
            headers=_auth_headers(owner["token"]),
            json={"tableZoneId": other_zone["id"], "tableNumber": "12A", "capacity": 4},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_ZONE_NOT_FOUND"

    def test_updating_an_unknown_id_returns_404(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        response = client.patch(
            f"/api/v1/branches/{branch['id']}/tables/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
            json={"tableZoneId": table_zone["id"], "tableNumber": "X", "capacity": 1},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    def test_renaming_to_a_number_already_used_by_a_sibling_table_is_a_conflict(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        _create_table(client, owner, branch["id"], table_zone["id"], tableNumber="Existing")
        table_b = _create_table(
            client, owner, branch["id"], table_zone["id"], tableNumber="ToRename"
        )

        response = client.patch(
            f"/api/v1/branches/{branch['id']}/tables/{table_b['id']}",
            headers=_auth_headers(owner["token"]),
            json={"tableZoneId": table_zone["id"], "tableNumber": "Existing", "capacity": 4},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "TABLE_NUMBER_ALREADY_EXISTS"

    def test_denied_without_table_manage(
        self, client: TestClient, owner: dict, reader_only: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        response = client.patch(
            f"/api/v1/branches/{branch['id']}/tables/{table['id']}",
            headers=_auth_headers(reader_only["token"]),
            json={"tableZoneId": table_zone["id"], "tableNumber": "Hijacked", "capacity": 4},
        )
        assert response.status_code == 403

    def test_idempotent_update_replays_on_the_same_key_and_body(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        body = {"tableZoneId": table_zone["id"], "tableNumber": "Renamed Once", "capacity": 5}
        url = f"/api/v1/branches/{branch['id']}/tables/{table['id']}"

        first = client.patch(url, headers=headers, json=body)
        second = client.patch(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_idempotency_key_conflict_on_a_different_body(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/tables/{table['id']}"

        first = client.patch(
            url,
            headers=headers,
            json={"tableZoneId": table_zone["id"], "tableNumber": "One", "capacity": 4},
        )
        assert first.status_code == 200, first.text

        second = client.patch(
            url,
            headers=headers,
            json={"tableZoneId": table_zone["id"], "tableNumber": "Two", "capacity": 4},
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestChangeTableStatus:
    def test_a_tenant_wide_manage_holder_can_change_status(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])

        response = client.post(
            f"/api/v1/tables/{table['id']}/status",
            headers=_auth_headers(owner["token"]),
            json={"status": "occupied"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "occupied"

    def test_every_valid_status_value_is_accepted(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        for value in ("available", "occupied", "reserved", "cleaning"):
            table = _create_table(
                client, owner, branch["id"], table_zone["id"], tableNumber=f"n-{value}"
            )
            response = client.post(
                f"/api/v1/tables/{table['id']}/status",
                headers=_auth_headers(owner["token"]),
                json={"status": value},
            )
            assert response.status_code == 200, response.text
            assert response.json()["data"]["status"] == value

    def test_an_invalid_status_value_is_rejected(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        response = client.post(
            f"/api/v1/tables/{table['id']}/status",
            headers=_auth_headers(owner["token"]),
            json={"status": "not-a-real-status"},
        )
        assert response.status_code == 422

    def test_an_unknown_table_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            f"/api/v1/tables/{'0' * 26}/status",
            headers=_auth_headers(owner["token"]),
            json={"status": "occupied"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    async def test_a_table_in_another_tenant_is_404_not_a_leak(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        other_tenant_id = generate_ulid()
        other_email = "other@example.com"
        other_user_id = await _seed_user(
            session_factory, tenant_id=other_tenant_id, email=other_email
        )
        await _grant_role(
            session_factory,
            tenant_id=other_tenant_id,
            user_id=other_user_id,
            permission_codes=frozenset({"restaurant.manage", "branch.manage", "table.manage"}),
        )
        other_token = _login_sync(client, tenant_id=other_tenant_id, email=other_email)
        other_restaurant = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(other_token),
            json={"legalName": "Other", "displayName": "Other", "defaultCurrencyCode": "USD"},
        ).json()["data"]
        other_branch = client.post(
            f"/api/v1/restaurants/{other_restaurant['id']}/branches",
            headers=_auth_headers(other_token),
            json={"name": "Other Branch"},
        ).json()["data"]
        other_zone = client.post(
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(other_token),
            json={"name": "Zone"},
        ).json()["data"]
        other_table = client.post(
            f"/api/v1/branches/{other_branch['id']}/tables",
            headers=_auth_headers(other_token),
            json=_create_body(other_zone["id"]),
        ).json()["data"]

        response = client.post(
            f"/api/v1/tables/{other_table['id']}/status",
            headers=_auth_headers(owner["token"]),
            json={"status": "occupied"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.post(f"/api/v1/tables/{'0' * 26}/status", json={"status": "occupied"})
        assert response.status_code == 401

    def test_denied_with_no_permission_anywhere(
        self, client: TestClient, no_permission: dict, branch: dict, owner: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        response = client.post(
            f"/api/v1/tables/{table['id']}/status",
            headers=_auth_headers(no_permission["token"]),
            json={"status": "occupied"},
        )
        assert response.status_code == 403

    def test_read_only_holder_is_denied(
        self, client: TestClient, owner: dict, reader_only: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        response = client.post(
            f"/api/v1/tables/{table['id']}/status",
            headers=_auth_headers(reader_only["token"]),
            json={"status": "occupied"},
        )
        assert response.status_code == 403

    async def test_a_branch_scoped_manage_holder_can_change_status_at_their_own_branch(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict, session_factory
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        email = "branchmgr@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/tables/{table['id']}/status",
            headers=_auth_headers(token),
            json={"status": "reserved"},
        )
        assert response.status_code == 200, response.text

    async def test_a_branch_scoped_manage_holder_cannot_change_status_at_a_different_branch(
        self,
        client: TestClient,
        owner: dict,
        restaurant_id: str,
        branch: dict,
        table_zone: dict,
        session_factory,
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        other_zone = client.post(
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json={"name": "Bar"},
        ).json()["data"]
        other_table = _create_table(client, owner, other_branch["id"], other_zone["id"])

        email = "scoped@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/tables/{other_table['id']}/status",
            headers=_auth_headers(token),
            json={"status": "occupied"},
        )
        assert response.status_code == 403

    async def test_denied_once_the_grant_is_revoked(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict, session_factory
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        email = "revoked@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        user_role_id = await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
        first = client.post(
            f"/api/v1/tables/{table['id']}/status",
            headers=_auth_headers(token),
            json={"status": "occupied"},
        )
        assert first.status_code == 200, first.text

        await _revoke_role(session_factory, tenant_id=owner["tenant_id"], user_role_id=user_role_id)

        second = client.post(
            f"/api/v1/tables/{table['id']}/status",
            headers=_auth_headers(token),
            json={"status": "cleaning"},
        )
        assert second.status_code == 403

    def test_idempotent_status_change_replays_on_the_same_key_and_body(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/tables/{table['id']}/status"
        body = {"status": "occupied"}

        first = client.post(url, headers=headers, json=body)
        second = client.post(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_idempotency_key_conflict_on_a_different_status(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict
    ) -> None:
        table = _create_table(client, owner, branch["id"], table_zone["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/tables/{table['id']}/status"

        first = client.post(url, headers=headers, json={"status": "occupied"})
        assert first.status_code == 200, first.text

        second = client.post(url, headers=headers, json={"status": "cleaning"})
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
