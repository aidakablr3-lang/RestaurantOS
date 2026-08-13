"""End-to-end HTTP tests for Restaurant CRUD against a real PostgreSQL
instance (Sprint 5 Step 4.1).

Follows test_rbac_router.py's exact pattern: dependency overrides
replace only the session factory and token service, so use cases,
repositories, RLS policies, and routing are all exercised exactly as in
production. Every test authenticates through a real POST /auth/login
call and seeds its own RBAC grant directly through the repositories,
mirroring how a real caller would arrive already-authorized.
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
                default_scope=RoleScope.TENANT,
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
                branch_id=None,
                granted_at=now,
                granted_by_user_id=None,
            )
        )


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def owner(session_factory, client: TestClient) -> AsyncGenerator[dict]:
    """A user holding both restaurant.read and restaurant.manage,
    tenant-wide -- the ordinary case for every happy-path test."""
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        permission_codes=frozenset({"restaurant.read", "restaurant.manage"}),
    )
    token = _login_sync(client, tenant_id=tenant_id, email=email)
    yield {"tenant_id": tenant_id, "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def reader_only(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    """A second user in owner's own tenant holding restaurant.read
    only -- proves read/write are gated independently."""
    email = "reader@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    await _grant_role(
        session_factory,
        tenant_id=owner["tenant_id"],
        user_id=user_id,
        permission_codes=frozenset({"restaurant.read"}),
    )
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def no_permission(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    """A third user in owner's tenant with zero RBAC grants."""
    email = "noperm@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def inactive_role_holder(
    session_factory, client: TestClient, owner: dict
) -> AsyncGenerator[dict]:
    """A user whose only grant is on an inactive Role -- must be
    denied identically to holding no grant at all."""
    email = "inactive@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    await _grant_role(
        session_factory,
        tenant_id=owner["tenant_id"],
        user_id=user_id,
        permission_codes=frozenset({"restaurant.read", "restaurant.manage"}),
        is_active=False,
    )
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


def _create_body(**overrides) -> dict:
    body = {
        "legalName": "Acme Restaurants Inc.",
        "displayName": "Acme",
        "defaultCurrencyCode": "USD",
    }
    body.update(overrides)
    return body


class TestCreateRestaurant:
    def test_a_manage_holder_can_create_a_restaurant(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["legalName"] == "Acme Restaurants Inc."
        assert data["displayName"] == "Acme"
        assert data["defaultCurrencyCode"] == "USD"
        assert data["status"] == "active"
        assert data["tenantId"] == owner["tenant_id"]

    def test_tenant_id_is_never_taken_from_the_client(
        self, client: TestClient, owner: dict
    ) -> None:
        """No tenantId field exists on the request schema at all --
        proving a client-supplied one (if somehow smuggled through
        extra JSON keys) is simply ignored, never trusted."""
        response = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(owner["token"]),
            json=_create_body(tenantId="01SOMEOTHERTENANTNOTMINEXX"),
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["tenantId"] == owner["tenant_id"]

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.post("/api/v1/restaurants", json=_create_body())
        assert response.status_code == 401

    def test_denied_without_restaurant_manage(self, client: TestClient, reader_only: dict) -> None:
        response = client.post(
            "/api/v1/restaurants", headers=_auth_headers(reader_only["token"]), json=_create_body()
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    def test_denied_with_no_permission_at_all(
        self, client: TestClient, no_permission: dict
    ) -> None:
        response = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(no_permission["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403, response.text

    def test_denied_when_the_only_grant_is_on_an_inactive_role(
        self, client: TestClient, inactive_role_holder: dict
    ) -> None:
        response = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(inactive_role_holder["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403, response.text

    def test_missing_required_field_is_rejected(self, client: TestClient, owner: dict) -> None:
        body = _create_body()
        del body["legalName"]
        response = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=body
        )
        assert response.status_code == 422

    def test_a_currency_code_of_the_wrong_length_is_rejected(
        self, client: TestClient, owner: dict
    ) -> None:
        response = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(owner["token"]),
            json=_create_body(defaultCurrencyCode="US"),
        )
        assert response.status_code == 422

    def test_an_empty_legal_name_is_rejected(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(owner["token"]),
            json=_create_body(legalName=""),
        )
        assert response.status_code == 422


class TestCreateRestaurantIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}

        first = client.post("/api/v1/restaurants", headers=headers, json=_create_body())
        second = client.post("/api/v1/restaurants", headers=headers, json=_create_body())

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json(), "a replay must return the exact original response"

        list_response = client.get("/api/v1/restaurants", headers=_auth_headers(owner["token"]))
        assert list_response.json()["meta"]["total"] == 1, (
            "the underlying use case must not have executed twice"
        )

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}

        first = client.post(
            "/api/v1/restaurants", headers=headers, json=_create_body(legalName="First Name")
        )
        assert first.status_code == 201, first.text

        second = client.post(
            "/api/v1/restaurants", headers=headers, json=_create_body(legalName="Different Name")
        )
        assert second.status_code == 409, second.text
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    def test_no_idempotency_key_means_no_deduplication(
        self, client: TestClient, owner: dict
    ) -> None:
        response_1 = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        )
        response_2 = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        )
        assert response_1.status_code == response_2.status_code == 201
        assert response_1.json()["data"]["id"] != response_2.json()["data"]["id"]


class TestGetRestaurant:
    def test_a_read_holder_can_get_a_restaurant(self, client: TestClient, owner: dict) -> None:
        create_response = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        )
        restaurant_id = create_response.json()["data"]["id"]

        response = client.get(
            f"/api/v1/restaurants/{restaurant_id}", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] == restaurant_id

    def test_unknown_id_returns_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(
            f"/api/v1/restaurants/{'0' * 26}", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESTAURANT_NOT_FOUND"

    async def test_a_restaurant_in_another_tenant_is_a_404_not_a_403(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        """Proves cross-tenant rejection never leaks existence -- a
        restaurant that genuinely exists, just in someone else's
        tenant, is indistinguishable from one that never existed."""
        other_tenant_id = generate_ulid()
        other_email = "other-owner@example.com"

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
            "/api/v1/restaurants", headers=_auth_headers(other_token), json=_create_body()
        ).json()["data"]

        response = client.get(
            f"/api/v1/restaurants/{other_restaurant['id']}", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESTAURANT_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.get(f"/api/v1/restaurants/{'0' * 26}")
        assert response.status_code == 401

    def test_denied_with_no_permission(self, client: TestClient, no_permission: dict) -> None:
        response = client.get(
            f"/api/v1/restaurants/{'0' * 26}", headers=_auth_headers(no_permission["token"])
        )
        assert response.status_code == 403


class TestListRestaurants:
    def test_lists_only_the_callers_own_tenant(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        for name in ("A", "B", "C"):
            client.post(
                "/api/v1/restaurants",
                headers=_auth_headers(owner["token"]),
                json=_create_body(legalName=name, displayName=name),
            )

        response = client.get("/api/v1/restaurants", headers=_auth_headers(owner["token"]))
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 3

    def test_pagination_offset_and_limit(self, client: TestClient, owner: dict) -> None:
        for i in range(5):
            client.post(
                "/api/v1/restaurants",
                headers=_auth_headers(owner["token"]),
                json=_create_body(legalName=f"R{i}", displayName=f"R{i}"),
            )

        page_1 = client.get(
            "/api/v1/restaurants?offset=0&limit=2", headers=_auth_headers(owner["token"])
        )
        page_2 = client.get(
            "/api/v1/restaurants?offset=2&limit=2", headers=_auth_headers(owner["token"])
        )

        assert page_1.status_code == page_2.status_code == 200
        assert len(page_1.json()["data"]) == 2
        assert len(page_2.json()["data"]) == 2
        assert page_1.json()["meta"]["total"] == 5
        ids_page_1 = {r["id"] for r in page_1.json()["data"]}
        ids_page_2 = {r["id"] for r in page_2.json()["data"]}
        assert ids_page_1.isdisjoint(ids_page_2)

    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.get("/api/v1/restaurants").status_code == 401

    def test_reader_only_can_list(self, client: TestClient, reader_only: dict) -> None:
        response = client.get("/api/v1/restaurants", headers=_auth_headers(reader_only["token"]))
        assert response.status_code == 200

    def test_denied_with_no_permission(self, client: TestClient, no_permission: dict) -> None:
        response = client.get("/api/v1/restaurants", headers=_auth_headers(no_permission["token"]))
        assert response.status_code == 403


class TestUpdateRestaurant:
    def test_a_manage_holder_can_update_a_restaurant(self, client: TestClient, owner: dict) -> None:
        restaurant_id = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        ).json()["data"]["id"]

        response = client.patch(
            f"/api/v1/restaurants/{restaurant_id}",
            headers=_auth_headers(owner["token"]),
            json=_create_body(legalName="Renamed Inc.", displayName="Renamed"),
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["legalName"] == "Renamed Inc."
        assert data["displayName"] == "Renamed"
        assert data["id"] == restaurant_id, "the identifier must never change"
        assert data["tenantId"] == owner["tenant_id"], "tenant ownership must never change"

    def test_updating_an_unknown_id_returns_404(self, client: TestClient, owner: dict) -> None:
        response = client.patch(
            f"/api/v1/restaurants/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404

    def test_denied_without_restaurant_manage(
        self, client: TestClient, owner: dict, reader_only: dict
    ) -> None:
        restaurant_id = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        ).json()["data"]["id"]

        response = client.patch(
            f"/api/v1/restaurants/{restaurant_id}",
            headers=_auth_headers(reader_only["token"]),
            json=_create_body(legalName="Hijacked"),
        )
        assert response.status_code == 403

    def test_idempotent_update_replays_on_the_same_key_and_body(
        self, client: TestClient, owner: dict
    ) -> None:
        restaurant_id = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        ).json()["data"]["id"]
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        body = _create_body(legalName="Renamed Once")

        first = client.patch(f"/api/v1/restaurants/{restaurant_id}", headers=headers, json=body)
        second = client.patch(f"/api/v1/restaurants/{restaurant_id}", headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_idempotency_key_conflict_on_a_different_body(
        self, client: TestClient, owner: dict
    ) -> None:
        restaurant_id = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        ).json()["data"]["id"]
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}

        first = client.patch(
            f"/api/v1/restaurants/{restaurant_id}",
            headers=headers,
            json=_create_body(legalName="Name One"),
        )
        assert first.status_code == 200, first.text

        second = client.patch(
            f"/api/v1/restaurants/{restaurant_id}",
            headers=headers,
            json=_create_body(legalName="Name Two"),
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestDiscontinueRestaurant:
    def test_discontinuing_transitions_status(self, client: TestClient, owner: dict) -> None:
        restaurant_id = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        ).json()["data"]["id"]

        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/discontinue",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "discontinued"

    def test_discontinuing_an_already_discontinued_restaurant_is_rejected(
        self, client: TestClient, owner: dict
    ) -> None:
        restaurant_id = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/restaurants/{restaurant_id}/discontinue",
            headers=_auth_headers(owner["token"]),
        )

        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/discontinue",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "INVALID_RESTAURANT_STATUS_TRANSITION"

    def test_no_hard_delete_endpoint_exists(self, client: TestClient, owner: dict) -> None:
        restaurant_id = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        ).json()["data"]["id"]

        response = client.delete(
            f"/api/v1/restaurants/{restaurant_id}", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 405, "DELETE must not be a registered method"

    def test_denied_without_restaurant_manage(
        self, client: TestClient, owner: dict, reader_only: dict
    ) -> None:
        restaurant_id = client.post(
            "/api/v1/restaurants", headers=_auth_headers(owner["token"]), json=_create_body()
        ).json()["data"]["id"]

        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/discontinue",
            headers=_auth_headers(reader_only["token"]),
        )
        assert response.status_code == 403
