"""End-to-end HTTP tests for Branch CRUD against a real PostgreSQL
instance (Sprint 5 Step 4.2).

Follows test_restaurant_router.py's exact pattern: dependency
overrides replace only the session factory and token service, so use
cases, repositories, RLS policies, and routing are all exercised
exactly as in production.
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
                name=f"Role {generate_ulid()}",
                description=None,
                default_scope=RoleScope.BRANCH if branch_id else RoleScope.TENANT,
                is_system=False,
                is_active=is_active,
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
    """A user holding branch.read/branch.manage tenant-wide."""
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        permission_codes=frozenset({"branch.read", "branch.manage", "restaurant.read"}),
    )
    token = _login_sync(client, tenant_id=tenant_id, email=email)
    yield {"tenant_id": tenant_id, "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def restaurant_id(session_factory, owner: dict) -> str:
    return await _create_restaurant(session_factory, owner["tenant_id"])


@pytest_asyncio.fixture
async def reader_only(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    email = "reader@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    await _grant_role(
        session_factory,
        tenant_id=owner["tenant_id"],
        user_id=user_id,
        permission_codes=frozenset({"branch.read"}),
    )
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def no_permission(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    email = "noperm@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def inactive_role_holder(
    session_factory, client: TestClient, owner: dict
) -> AsyncGenerator[dict]:
    email = "inactive@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    await _grant_role(
        session_factory,
        tenant_id=owner["tenant_id"],
        user_id=user_id,
        permission_codes=frozenset({"branch.read", "branch.manage"}),
        is_active=False,
    )
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


def _create_body(**overrides) -> dict:
    body = {"name": "Downtown"}
    body.update(overrides)
    return body


def _create_branch(client: TestClient, owner: dict, restaurant_id: str, **overrides) -> dict:
    response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches",
        headers=_auth_headers(owner["token"]),
        json=_create_body(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestCreateBranch:
    def test_a_manage_holder_can_create_a_branch(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["name"] == "Downtown"
        assert data["status"] == "active"
        assert data["restaurantId"] == restaurant_id
        assert data["tenantId"] == owner["tenant_id"]
        assert data["address"] is None

    def test_creating_with_an_address_persists_it(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(
                address={
                    "line1": "123 Main St",
                    "city": "Springfield",
                    "countryCode": "US",
                    "postalCode": "00000",
                }
            ),
        )
        assert response.status_code == 201, response.text
        address = response.json()["data"]["address"]
        assert address is not None
        assert address["line1"] == "123 Main St"
        assert address["city"] == "Springfield"
        assert address["countryCode"] == "US"
        assert address["postalCode"] == "00000"

    def test_creating_with_a_valid_gstin_persists_it(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(gstin="29ABCDE1234F1Z5"),
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["gstin"] == "29ABCDE1234F1Z5"

    def test_a_malformed_gstin_is_rejected(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        # The exact shape a fraction/lowercase/wrong-length mistake would
        # produce -- 14 characters, one short of the real 15.
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(gstin="29ABCDE1234F1Z"),
        )
        assert response.status_code == 422

    def test_creating_without_an_address_is_allowed(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["address"] is None

    def test_an_unknown_restaurant_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            f"/api/v1/restaurants/{'0' * 26}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESTAURANT_NOT_FOUND"

    async def test_a_restaurant_belonging_to_another_tenant_is_404_not_a_leak(
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
            permission_codes=frozenset({"restaurant.manage"}),
        )
        other_token = _login_sync(client, tenant_id=other_tenant_id, email=other_email)
        other_restaurant = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(other_token),
            json={"legalName": "Other", "displayName": "Other", "defaultCurrencyCode": "USD"},
        ).json()["data"]

        response = client.post(
            f"/api/v1/restaurants/{other_restaurant['id']}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESTAURANT_NOT_FOUND"

    def test_a_duplicate_name_under_the_same_restaurant_is_a_conflict(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        _create_branch(client, owner, restaurant_id, name="North")

        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="North"),
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "BRANCH_NAME_CONFLICT"

    async def test_the_same_name_under_a_different_restaurant_is_allowed(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        restaurant_a = await _create_restaurant(session_factory, owner["tenant_id"], name="RA")
        restaurant_b = await _create_restaurant(session_factory, owner["tenant_id"], name="RB")

        response_a = client.post(
            f"/api/v1/restaurants/{restaurant_a}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Main"),
        )
        response_b = client.post(
            f"/api/v1/restaurants/{restaurant_b}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Main"),
        )
        assert response_a.status_code == 201, response_a.text
        assert response_b.status_code == 201, response_b.text

    def test_requires_authentication(self, client: TestClient, restaurant_id: str) -> None:
        response = client.post(f"/api/v1/restaurants/{restaurant_id}/branches", json=_create_body())
        assert response.status_code == 401

    def test_denied_without_branch_manage(
        self, client: TestClient, reader_only: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(reader_only["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(no_permission["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    def test_denied_when_the_only_grant_is_on_an_inactive_role(
        self, client: TestClient, inactive_role_holder: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(inactive_role_holder["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    def test_missing_required_field_is_rejected(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={},
        )
        assert response.status_code == 422

    def test_an_empty_name_is_rejected(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name=""),
        )
        assert response.status_code == 422


class TestCreateBranchIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/restaurants/{restaurant_id}/branches"

        first = client.post(url, headers=headers, json=_create_body())
        second = client.post(url, headers=headers, json=_create_body())

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()

        list_response = client.get("/api/v1/branches", headers=_auth_headers(owner["token"]))
        assert list_response.json()["meta"]["total"] == 1

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/restaurants/{restaurant_id}/branches"

        first = client.post(url, headers=headers, json=_create_body(name="First"))
        assert first.status_code == 201, first.text

        second = client.post(url, headers=headers, json=_create_body(name="Second"))
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestGetBranch:
    def test_a_read_holder_can_get_a_branch(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        response = client.get(
            f"/api/v1/branches/{branch['id']}", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] == branch["id"]

    def test_unknown_id_returns_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(f"/api/v1/branches/{'0' * 26}", headers=_auth_headers(owner["token"]))
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    async def test_a_branch_in_another_tenant_is_a_404_not_a_403(
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
            json=_create_body(),
        ).json()["data"]

        response = client.get(
            f"/api/v1/branches/{other_branch['id']}", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    async def test_branch_scoped_grant_can_read_its_own_branch(
        self, client: TestClient, owner: dict, restaurant_id: str, session_factory
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        email = "branchmgr@example.com"

        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"branch.read"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.get(f"/api/v1/branches/{branch['id']}", headers=_auth_headers(token))
        assert response.status_code == 200, response.text

    async def test_branch_scoped_grant_cannot_read_a_different_branch(
        self, client: TestClient, owner: dict, restaurant_id: str, session_factory
    ) -> None:
        branch_a = _create_branch(client, owner, restaurant_id, name="A")
        branch_b = _create_branch(client, owner, restaurant_id, name="B")
        email = "scoped@example.com"

        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"branch.read"}),
            branch_id=branch_a["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.get(f"/api/v1/branches/{branch_b['id']}", headers=_auth_headers(token))
        assert response.status_code == 403

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.get(f"/api/v1/branches/{'0' * 26}")
        assert response.status_code == 401


class TestListBranches:
    def test_lists_only_the_callers_own_tenant(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        for name in ("A", "B", "C"):
            _create_branch(client, owner, restaurant_id, name=name)

        response = client.get("/api/v1/branches", headers=_auth_headers(owner["token"]))
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 3

    def test_pagination_offset_and_limit(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        for i in range(5):
            _create_branch(client, owner, restaurant_id, name=f"B{i}")

        page_1 = client.get(
            "/api/v1/branches?offset=0&limit=2", headers=_auth_headers(owner["token"])
        )
        page_2 = client.get(
            "/api/v1/branches?offset=2&limit=2", headers=_auth_headers(owner["token"])
        )
        assert len(page_1.json()["data"]) == 2
        assert len(page_2.json()["data"]) == 2
        assert page_1.json()["meta"]["total"] == 5
        ids_1 = {b["id"] for b in page_1.json()["data"]}
        ids_2 = {b["id"] for b in page_2.json()["data"]}
        assert ids_1.isdisjoint(ids_2)

    async def test_a_branch_scoped_reader_sees_only_their_own_branch(
        self, client: TestClient, owner: dict, restaurant_id: str, session_factory
    ) -> None:
        branch_a = _create_branch(client, owner, restaurant_id, name="A")
        _create_branch(client, owner, restaurant_id, name="B")
        email = "scoped-list@example.com"

        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"branch.read"}),
            branch_id=branch_a["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.get("/api/v1/branches", headers=_auth_headers(token))
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 1
        assert response.json()["data"][0]["id"] == branch_a["id"]

    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.get("/api/v1/branches").status_code == 401

    def test_denied_with_no_permission(self, client: TestClient, no_permission: dict) -> None:
        response = client.get("/api/v1/branches", headers=_auth_headers(no_permission["token"]))
        assert response.status_code == 403


class TestUpdateBranch:
    def test_a_manage_holder_can_update_name(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)

        response = client.patch(
            f"/api/v1/branches/{branch['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": "Renamed"},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["name"] == "Renamed"
        assert data["id"] == branch["id"]
        assert data["restaurantId"] == restaurant_id
        assert data["tenantId"] == owner["tenant_id"]

    def test_adding_an_address_on_update_persists_it(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        assert branch["address"] is None

        response = client.patch(
            f"/api/v1/branches/{branch['id']}",
            headers=_auth_headers(owner["token"]),
            json={
                "name": branch["name"],
                "address": {"line1": "1 First Ave", "city": "Metropolis"},
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["address"]["line1"] == "1 First Ave"

    def test_updating_an_existing_address_edits_it_in_place(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        create_response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(address={"line1": "Old St", "city": "Old City"}),
        )
        branch = create_response.json()["data"]
        original_address_id = branch["address"]["id"]

        response = client.patch(
            f"/api/v1/branches/{branch['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": branch["name"], "address": {"line1": "New St", "city": "New City"}},
        )
        assert response.status_code == 200, response.text
        updated_address = response.json()["data"]["address"]
        assert updated_address["id"] == original_address_id, "must edit in place, not replace"
        assert updated_address["line1"] == "New St"
        assert updated_address["city"] == "New City"

    def test_omitting_address_leaves_it_untouched(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        create_response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(address={"line1": "Keep Me", "city": "Keepville"}),
        )
        branch = create_response.json()["data"]

        response = client.patch(
            f"/api/v1/branches/{branch['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": "New Name Only"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["address"]["line1"] == "Keep Me"

    def test_setting_a_gstin_on_update_persists_it(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)

        response = client.patch(
            f"/api/v1/branches/{branch['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": branch["name"], "gstin": "29ABCDE1234F1Z5"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["gstin"] == "29ABCDE1234F1Z5"

    def test_omitting_gstin_on_update_leaves_it_untouched(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        create_response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json=_create_body(gstin="29ABCDE1234F1Z5"),
        )
        branch = create_response.json()["data"]

        response = client.patch(
            f"/api/v1/branches/{branch['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": "New Name Only"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["gstin"] == "29ABCDE1234F1Z5"

    def test_a_malformed_gstin_on_update_is_rejected(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)

        response = client.patch(
            f"/api/v1/branches/{branch['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": branch["name"], "gstin": "not-a-gstin"},
        )
        assert response.status_code == 422

    def test_updating_an_unknown_id_returns_404(self, client: TestClient, owner: dict) -> None:
        response = client.patch(
            f"/api/v1/branches/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
            json={"name": "X"},
        )
        assert response.status_code == 404

    def test_renaming_to_a_name_already_used_by_a_sibling_branch_is_a_conflict(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        _create_branch(client, owner, restaurant_id, name="Existing")
        branch_b = _create_branch(client, owner, restaurant_id, name="ToRename")

        response = client.patch(
            f"/api/v1/branches/{branch_b['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": "Existing"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "BRANCH_NAME_CONFLICT"

    def test_denied_without_branch_manage(
        self, client: TestClient, owner: dict, reader_only: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        response = client.patch(
            f"/api/v1/branches/{branch['id']}",
            headers=_auth_headers(reader_only["token"]),
            json={"name": "Hijacked"},
        )
        assert response.status_code == 403

    def test_idempotent_update_replays_on_the_same_key_and_body(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        body = {"name": "Renamed Once"}

        first = client.patch(f"/api/v1/branches/{branch['id']}", headers=headers, json=body)
        second = client.patch(f"/api/v1/branches/{branch['id']}", headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_idempotency_key_conflict_on_a_different_body(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}

        first = client.patch(
            f"/api/v1/branches/{branch['id']}", headers=headers, json={"name": "Name One"}
        )
        assert first.status_code == 200, first.text

        second = client.patch(
            f"/api/v1/branches/{branch['id']}", headers=headers, json={"name": "Name Two"}
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestBranchLifecycle:
    def test_close_transitions_to_temporarily_closed(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)

        response = client.post(
            f"/api/v1/branches/{branch['id']}/close", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "temporarily_closed"

    def test_reopen_transitions_back_to_active(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        client.post(f"/api/v1/branches/{branch['id']}/close", headers=_auth_headers(owner["token"]))

        response = client.post(
            f"/api/v1/branches/{branch['id']}/reopen", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "active"

    def test_reopening_an_already_active_branch_is_rejected(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)

        response = client.post(
            f"/api/v1/branches/{branch['id']}/reopen", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_BRANCH_STATUS_TRANSITION"

    def test_closing_an_already_closed_branch_is_rejected(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        client.post(f"/api/v1/branches/{branch['id']}/close", headers=_auth_headers(owner["token"]))

        response = client.post(
            f"/api/v1/branches/{branch['id']}/close", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_BRANCH_STATUS_TRANSITION"

    def test_denied_without_branch_manage(
        self, client: TestClient, owner: dict, reader_only: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        response = client.post(
            f"/api/v1/branches/{branch['id']}/close", headers=_auth_headers(reader_only["token"])
        )
        assert response.status_code == 403

    def test_no_permanent_close_endpoint_exists(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        branch = _create_branch(client, owner, restaurant_id)
        response = client.post(
            f"/api/v1/branches/{branch['id']}/close-permanently",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404, "no such route is registered"
