"""End-to-end HTTP tests for /api/v1/auth/* against a real PostgreSQL instance.

Requires TEST_DATABASE_URL (see tests/integration/conftest.py). Dependency
overrides replace only the session factory and token service (so tests
don't depend on JWT_PRIVATE_KEY/JWT_PUBLIC_KEY env vars being set) — the
password hasher, use cases, repositories, and routing are all exercised
exactly as in production.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import text

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.main import create_app
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


@pytest_asyncio.fixture
async def tenant_and_user(session_factory) -> AsyncGenerator[dict[str, str]]:
    tenant_id = generate_ulid()
    user_id = generate_ulid()
    password_hash = Argon2PasswordHasher().hash(PASSWORD)

    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO tenants (id, legal_name, display_name, tenant_tier, status, "
                "default_currency_code) VALUES (:id, 'Acme', 'Acme', 'shared', 'active', 'USD')"
            ),
            {"id": tenant_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash, permission_version, "
                "status) VALUES (:id, :tenant_id, :email, :password_hash, 1, 'active')"
            ),
            {
                "id": user_id,
                "tenant_id": tenant_id,
                "email": "owner@example.com",
                "password_hash": password_hash,
            },
        )

    yield {"tenant_id": tenant_id, "user_id": user_id, "email": "owner@example.com"}


class TestLoginEndpoint:
    def test_returns_token_pair_for_valid_credentials(
        self, client: TestClient, tenant_and_user: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "tenantId": tenant_and_user["tenant_id"],
                "email": tenant_and_user["email"],
                "password": PASSWORD,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["tokenType"] == "bearer"
        assert body["data"]["accessToken"]
        assert body["data"]["refreshToken"]

    def test_returns_401_for_wrong_password(
        self, client: TestClient, tenant_and_user: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "tenantId": tenant_and_user["tenant_id"],
                "email": tenant_and_user["email"],
                "password": "wrong password",
            },
        )

        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "INVALID_CREDENTIALS"

    def test_returns_422_for_malformed_request_body(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/login", json={"email": "not-enough-fields"})
        assert response.status_code == 422


class TestRefreshEndpoint:
    def test_refresh_rotates_the_session_and_returns_new_tokens(
        self, client: TestClient, tenant_and_user: dict[str, str]
    ) -> None:
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "tenantId": tenant_and_user["tenant_id"],
                "email": tenant_and_user["email"],
                "password": PASSWORD,
            },
        )
        original_refresh_token = login_response.json()["data"]["refreshToken"]

        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={
                "tenantId": tenant_and_user["tenant_id"],
                "refreshToken": original_refresh_token,
            },
        )

        assert refresh_response.status_code == 200
        new_refresh_token = refresh_response.json()["data"]["refreshToken"]
        assert new_refresh_token != original_refresh_token

        # The rotated-out token must no longer work.
        reuse_response = client.post(
            "/api/v1/auth/refresh",
            json={
                "tenantId": tenant_and_user["tenant_id"],
                "refreshToken": original_refresh_token,
            },
        )
        assert reuse_response.status_code == 401


class TestLogoutEndpoint:
    def test_logout_revokes_the_session_so_it_can_no_longer_refresh(
        self, client: TestClient, tenant_and_user: dict[str, str]
    ) -> None:
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "tenantId": tenant_and_user["tenant_id"],
                "email": tenant_and_user["email"],
                "password": PASSWORD,
            },
        )
        refresh_token = login_response.json()["data"]["refreshToken"]

        logout_response = client.post(
            "/api/v1/auth/logout",
            json={"tenantId": tenant_and_user["tenant_id"], "refreshToken": refresh_token},
        )
        assert logout_response.status_code == 204

        refresh_after_logout = client.post(
            "/api/v1/auth/refresh",
            json={"tenantId": tenant_and_user["tenant_id"], "refreshToken": refresh_token},
        )
        assert refresh_after_logout.status_code == 401

    def test_logout_is_idempotent(
        self, client: TestClient, tenant_and_user: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/auth/logout",
            json={
                "tenantId": tenant_and_user["tenant_id"],
                "refreshToken": "never-issued-token",
            },
        )
        assert response.status_code == 204
