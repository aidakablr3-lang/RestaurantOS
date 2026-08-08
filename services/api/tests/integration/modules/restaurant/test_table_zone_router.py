"""End-to-end HTTP tests for TableZone (Dining Areas) CRUD against a
real PostgreSQL instance (Sprint 5 Step 4.4).

Follows test_branch_router.py's exact pattern: dependency overrides
replace only the session factory and token service, so use cases,
repositories, RLS policies, and routing are all exercised exactly as
in production. Every route is nested under a specific branch (see
table_zone_router.py's own docstring for why), so authorization is
gated by `table.manage`/`table.read` via `require_branch_permission`
reading the URL's own `branch_id` -- exactly like Branch's own
sub-resource routes and Operating Hours.
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


def _create_body(**overrides) -> dict:
    body = {"name": "Patio"}
    body.update(overrides)
    return body


def _create_table_zone(client: TestClient, owner: dict, branch_id: str, **overrides) -> dict:
    response = client.post(
        f"/api/v1/branches/{branch_id}/table-zones",
        headers=_auth_headers(owner["token"]),
        json=_create_body(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestCreateTableZone:
    def test_a_manage_holder_can_create_a_table_zone(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json=_create_body(display_order=2),
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["name"] == "Patio"
        assert data["displayOrder"] == 2
        assert data["branchId"] == branch["id"]
        assert data["tenantId"] == owner["tenant_id"]

    def test_defaults_display_order_to_zero(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        data = _create_table_zone(client, owner, branch["id"])
        assert data["displayOrder"] == 0

    def test_an_unknown_branch_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            f"/api/v1/branches/{'0' * 26}/table-zones",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    async def test_a_branch_belonging_to_another_tenant_is_404_not_a_leak(
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
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_a_duplicate_name_under_the_same_branch_is_a_conflict(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        _create_table_zone(client, owner, branch["id"], name="Patio")

        response = client.post(
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Patio"),
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "TABLE_ZONE_NAME_CONFLICT"

    async def test_the_same_name_under_a_different_branch_is_allowed(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch_a = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "BA"},
        ).json()["data"]
        branch_b = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "BB"},
        ).json()["data"]

        response_a = client.post(
            f"/api/v1/branches/{branch_a['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Main"),
        )
        response_b = client.post(
            f"/api/v1/branches/{branch_b['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Main"),
        )
        assert response_a.status_code == 201, response_a.text
        assert response_b.status_code == 201, response_b.text

    def test_requires_authentication(self, client: TestClient, branch: dict) -> None:
        response = client.post(f"/api/v1/branches/{branch['id']}/table-zones", json=_create_body())
        assert response.status_code == 401

    def test_denied_without_table_manage(
        self, client: TestClient, reader_only: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(reader_only["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(no_permission["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    async def test_denied_when_the_only_grant_is_on_an_inactive_role(
        self, client: TestClient, owner: dict, branch: dict, session_factory
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
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(token),
            json=_create_body(),
        )
        assert response.status_code == 403

    async def test_denied_once_the_grant_is_revoked(
        self, client: TestClient, owner: dict, branch: dict, session_factory
    ) -> None:
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
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(token),
            json=_create_body(name="First"),
        )
        assert first.status_code == 201, first.text

        await _revoke_role(session_factory, tenant_id=owner["tenant_id"], user_role_id=user_role_id)

        second = client.post(
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(token),
            json=_create_body(name="Second"),
        )
        assert second.status_code == 403

    async def test_a_branch_scoped_manage_grant_can_create_in_its_own_branch(
        self, client: TestClient, owner: dict, branch: dict, session_factory
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
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(token),
            json=_create_body(),
        )
        assert response.status_code == 201, response.text

    async def test_a_branch_scoped_manage_grant_cannot_create_in_a_different_branch(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict, session_factory
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
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(token),
            json=_create_body(),
        )
        assert response.status_code == 403

    def test_missing_required_field_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json={},
        )
        assert response.status_code == 422

    def test_an_empty_name_is_rejected(self, client: TestClient, owner: dict, branch: dict) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name=""),
        )
        assert response.status_code == 422


class TestCreateTableZoneIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/table-zones"

        first = client.post(url, headers=headers, json=_create_body())
        second = client.post(url, headers=headers, json=_create_body())

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()

        list_response = client.get(url, headers=_auth_headers(owner["token"]))
        assert list_response.json()["meta"]["total"] == 1

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/table-zones"

        first = client.post(url, headers=headers, json=_create_body(name="First"))
        assert first.status_code == 201, first.text

        second = client.post(url, headers=headers, json=_create_body(name="Second"))
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestGetTableZone:
    def test_a_read_holder_can_get_a_table_zone(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        table_zone = _create_table_zone(client, owner, branch["id"])
        response = client.get(
            f"/api/v1/branches/{branch['id']}/table-zones/{table_zone['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] == table_zone["id"]

    def test_unknown_id_returns_404(self, client: TestClient, owner: dict, branch: dict) -> None:
        response = client.get(
            f"/api/v1/branches/{branch['id']}/table-zones/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_ZONE_NOT_FOUND"

    async def test_a_table_zone_belonging_to_a_different_branch_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        other_zone = _create_table_zone(client, owner, other_branch["id"])

        response = client.get(
            f"/api/v1/branches/{branch['id']}/table-zones/{other_zone['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_ZONE_NOT_FOUND"

    async def test_a_table_zone_in_another_tenant_is_a_404_not_a_403(
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
            json=_create_body(),
        ).json()["data"]

        response = client.get(
            f"/api/v1/branches/{branch['id']}/table-zones/{other_zone['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_ZONE_NOT_FOUND"

    async def test_branch_scoped_grant_can_read_its_own_branchs_zone(
        self, client: TestClient, owner: dict, branch: dict, session_factory
    ) -> None:
        table_zone = _create_table_zone(client, owner, branch["id"])
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
            f"/api/v1/branches/{branch['id']}/table-zones/{table_zone['id']}",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text

    async def test_branch_scoped_grant_cannot_read_a_different_branchs_zone(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict, session_factory
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        other_zone = _create_table_zone(client, owner, other_branch["id"])
        email = "scoped@example.com"

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
            f"/api/v1/branches/{other_branch['id']}/table-zones/{other_zone['id']}",
            headers=_auth_headers(token),
        )
        assert response.status_code == 403

    def test_requires_authentication(self, client: TestClient, branch: dict) -> None:
        response = client.get(f"/api/v1/branches/{branch['id']}/table-zones/{'0' * 26}")
        assert response.status_code == 401


class TestListTableZones:
    def test_lists_only_the_requested_branchs_zones(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        for name in ("A", "B", "C"):
            _create_table_zone(client, owner, branch["id"], name=name)

        response = client.get(
            f"/api/v1/branches/{branch['id']}/table-zones", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 3

    def test_ordered_deterministically_by_display_order(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        _create_table_zone(client, owner, branch["id"], name="C", display_order=2)
        _create_table_zone(client, owner, branch["id"], name="A", display_order=0)
        _create_table_zone(client, owner, branch["id"], name="B", display_order=1)

        response = client.get(
            f"/api/v1/branches/{branch['id']}/table-zones", headers=_auth_headers(owner["token"])
        )
        assert [tz["name"] for tz in response.json()["data"]] == ["A", "B", "C"]

    def test_pagination_offset_and_limit(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        for i in range(5):
            _create_table_zone(client, owner, branch["id"], name=f"Z{i}", display_order=i)

        page_1 = client.get(
            f"/api/v1/branches/{branch['id']}/table-zones?offset=0&limit=2",
            headers=_auth_headers(owner["token"]),
        )
        page_2 = client.get(
            f"/api/v1/branches/{branch['id']}/table-zones?offset=2&limit=2",
            headers=_auth_headers(owner["token"]),
        )
        assert len(page_1.json()["data"]) == 2
        assert len(page_2.json()["data"]) == 2
        assert page_1.json()["meta"]["total"] == 5
        ids_1 = {tz["id"] for tz in page_1.json()["data"]}
        ids_2 = {tz["id"] for tz in page_2.json()["data"]}
        assert ids_1.isdisjoint(ids_2)

    def test_an_unknown_branch_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(
            f"/api/v1/branches/{'0' * 26}/table-zones", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, branch: dict) -> None:
        response = client.get(f"/api/v1/branches/{branch['id']}/table-zones")
        assert response.status_code == 401

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, branch: dict
    ) -> None:
        response = client.get(
            f"/api/v1/branches/{branch['id']}/table-zones",
            headers=_auth_headers(no_permission["token"]),
        )
        assert response.status_code == 403


class TestUpdateTableZone:
    def test_a_manage_holder_can_update_name_and_display_order(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        table_zone = _create_table_zone(client, owner, branch["id"])

        response = client.patch(
            f"/api/v1/branches/{branch['id']}/table-zones/{table_zone['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": "Renamed", "displayOrder": 7},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["name"] == "Renamed"
        assert data["displayOrder"] == 7
        assert data["id"] == table_zone["id"]

    def test_updating_an_unknown_id_returns_404(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.patch(
            f"/api/v1/branches/{branch['id']}/table-zones/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
            json={"name": "X", "displayOrder": 0},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_ZONE_NOT_FOUND"

    async def test_updating_a_zone_belonging_to_a_different_branch_returns_404(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        other_zone = _create_table_zone(client, owner, other_branch["id"])

        response = client.patch(
            f"/api/v1/branches/{branch['id']}/table-zones/{other_zone['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": "Hijacked", "displayOrder": 0},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_ZONE_NOT_FOUND"

    def test_renaming_to_a_name_already_used_by_a_sibling_zone_is_a_conflict(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        _create_table_zone(client, owner, branch["id"], name="Existing")
        zone_b = _create_table_zone(client, owner, branch["id"], name="ToRename")

        response = client.patch(
            f"/api/v1/branches/{branch['id']}/table-zones/{zone_b['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": "Existing", "displayOrder": 0},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "TABLE_ZONE_NAME_CONFLICT"

    def test_denied_without_table_manage(
        self, client: TestClient, owner: dict, reader_only: dict, branch: dict
    ) -> None:
        table_zone = _create_table_zone(client, owner, branch["id"])
        response = client.patch(
            f"/api/v1/branches/{branch['id']}/table-zones/{table_zone['id']}",
            headers=_auth_headers(reader_only["token"]),
            json={"name": "Hijacked", "displayOrder": 0},
        )
        assert response.status_code == 403

    def test_idempotent_update_replays_on_the_same_key_and_body(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        table_zone = _create_table_zone(client, owner, branch["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        body = {"name": "Renamed Once", "displayOrder": 1}
        url = f"/api/v1/branches/{branch['id']}/table-zones/{table_zone['id']}"

        first = client.patch(url, headers=headers, json=body)
        second = client.patch(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_idempotency_key_conflict_on_a_different_body(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        table_zone = _create_table_zone(client, owner, branch["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/table-zones/{table_zone['id']}"

        first = client.patch(url, headers=headers, json={"name": "Name One", "displayOrder": 0})
        assert first.status_code == 200, first.text

        second = client.patch(url, headers=headers, json={"name": "Name Two", "displayOrder": 0})
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
