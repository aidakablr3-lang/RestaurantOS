"""End-to-end HTTP tests for /api/v1/users against a real PostgreSQL
instance -- the real API counterpart to scripts/create_user.py.

Follows test_rbac_router.py's pattern exactly, including its own
bootstrap rationale: there is no self-service path to grant yourself
roles.assign, so every test seeds one user's Tenant Owner grant
directly through the repositories before driving the rest of the flow
over real HTTP (mirrors scripts/backfill_tenant_owner.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
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


def _login(client: TestClient, *, tenant_id: str, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"tenantId": tenant_id, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["accessToken"]


async def _grant_tenant_owner(session_factory, *, tenant_id: str, user_id: str) -> None:
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
        await role_permission_repo.replace_for_role(role.id, frozenset({"roles.assign"}))
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


class TestCreateUser:
    async def test_a_roles_assign_holder_can_create_a_user_with_a_generated_password(
        self, client: TestClient, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        owner_id = await _seed_user(session_factory, tenant_id=tenant_id, email="owner@example.com")
        await _grant_tenant_owner(session_factory, tenant_id=tenant_id, user_id=owner_id)
        owner_token = _login(client, tenant_id=tenant_id, email="owner@example.com")

        response = client.post(
            "/api/v1/users",
            headers=_auth_headers(owner_token),
            json={"email": "waiter@example.com"},
        )

        assert response.status_code == 201, response.text
        body = response.json()["data"]
        assert body["email"] == "waiter@example.com"
        assert body["status"] == "active"
        assert body["generatedPassword"] is not None

        # The created account can really log in with that password.
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "tenantId": tenant_id,
                "email": "waiter@example.com",
                "password": body["generatedPassword"],
            },
        )
        assert login_response.status_code == 200, login_response.text

    async def test_a_caller_supplied_password_is_not_echoed_back(
        self, client: TestClient, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        owner_id = await _seed_user(session_factory, tenant_id=tenant_id, email="owner2@example.com")
        await _grant_tenant_owner(session_factory, tenant_id=tenant_id, user_id=owner_id)
        owner_token = _login(client, tenant_id=tenant_id, email="owner2@example.com")

        response = client.post(
            "/api/v1/users",
            headers=_auth_headers(owner_token),
            json={"email": "manager@example.com", "password": "a specific known password"},
        )

        assert response.status_code == 201, response.text
        assert response.json()["data"]["generatedPassword"] is None

    async def test_duplicate_email_is_rejected(self, client: TestClient, session_factory) -> None:
        tenant_id = generate_ulid()
        owner_id = await _seed_user(session_factory, tenant_id=tenant_id, email="owner3@example.com")
        await _grant_tenant_owner(session_factory, tenant_id=tenant_id, user_id=owner_id)
        owner_token = _login(client, tenant_id=tenant_id, email="owner3@example.com")
        payload = {"email": "dup@example.com"}

        first = client.post("/api/v1/users", headers=_auth_headers(owner_token), json=payload)
        assert first.status_code == 201

        second = client.post("/api/v1/users", headers=_auth_headers(owner_token), json=payload)
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "USER_EMAIL_CONFLICT"

    async def test_a_caller_without_roles_assign_is_rejected(
        self, client: TestClient, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        await _seed_user(session_factory, tenant_id=tenant_id, email="nobody@example.com")
        token = _login(client, tenant_id=tenant_id, email="nobody@example.com")

        response = client.post(
            "/api/v1/users", headers=_auth_headers(token), json={"email": "sneaky@example.com"}
        )
        assert response.status_code == 403

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.post("/api/v1/users", json={"email": "no-auth@example.com"})
        assert response.status_code == 401


class TestListUsers:
    async def test_lists_users_created_in_the_tenant(
        self, client: TestClient, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        owner_id = await _seed_user(session_factory, tenant_id=tenant_id, email="owner4@example.com")
        await _grant_tenant_owner(session_factory, tenant_id=tenant_id, user_id=owner_id)
        owner_token = _login(client, tenant_id=tenant_id, email="owner4@example.com")
        client.post(
            "/api/v1/users", headers=_auth_headers(owner_token), json={"email": "staff1@example.com"}
        )

        response = client.get("/api/v1/users", headers=_auth_headers(owner_token))

        assert response.status_code == 200
        body = response.json()
        emails = {u["email"] for u in body["data"]}
        assert "owner4@example.com" in emails
        assert "staff1@example.com" in emails
        assert body["meta"]["total"] >= 2

    async def test_another_tenants_users_are_never_listed(
        self, client: TestClient, session_factory
    ) -> None:
        tenant_a = generate_ulid()
        tenant_b = generate_ulid()
        owner_a = await _seed_user(session_factory, tenant_id=tenant_a, email="owner-a@example.com")
        await _grant_tenant_owner(session_factory, tenant_id=tenant_a, user_id=owner_a)
        await _seed_user(session_factory, tenant_id=tenant_b, email="owner-b@example.com")
        owner_a_token = _login(client, tenant_id=tenant_a, email="owner-a@example.com")

        response = client.get("/api/v1/users", headers=_auth_headers(owner_a_token))

        assert response.status_code == 200
        emails = {u["email"] for u in response.json()["data"]}
        assert "owner-b@example.com" not in emails


class TestCreateUserIdempotency:
    async def test_same_key_and_payload_returns_the_original_user_with_no_duplicate(
        self, client: TestClient, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        owner_id = await _seed_user(session_factory, tenant_id=tenant_id, email="idem-owner@example.com")
        await _grant_tenant_owner(session_factory, tenant_id=tenant_id, user_id=owner_id)
        owner_token = _login(client, tenant_id=tenant_id, email="idem-owner@example.com")
        headers = {**_auth_headers(owner_token), "Idempotency-Key": "create-user-key-1"}
        payload = {"email": "idem-waiter@example.com"}

        first = client.post("/api/v1/users", headers=headers, json=payload)
        second = client.post("/api/v1/users", headers=headers, json=payload)

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["data"]["id"] == second.json()["data"]["id"]

        list_response = client.get("/api/v1/users", headers=_auth_headers(owner_token))
        matching = [
            u for u in list_response.json()["data"] if u["email"] == "idem-waiter@example.com"
        ]
        assert len(matching) == 1

    async def test_same_key_with_a_different_payload_is_a_conflict(
        self, client: TestClient, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        owner_id = await _seed_user(session_factory, tenant_id=tenant_id, email="idem-owner2@example.com")
        await _grant_tenant_owner(session_factory, tenant_id=tenant_id, user_id=owner_id)
        owner_token = _login(client, tenant_id=tenant_id, email="idem-owner2@example.com")
        headers = {**_auth_headers(owner_token), "Idempotency-Key": "create-user-key-2"}

        first = client.post(
            "/api/v1/users", headers=headers, json={"email": "idem-first@example.com"}
        )
        assert first.status_code == 201, first.text

        second = client.post(
            "/api/v1/users", headers=headers, json={"email": "idem-second@example.com"}
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
