"""End-to-end HTTP tests for POST /api/v1/owner-activation against real
PostgreSQL (Phase 1 design doc SSA.4).

Covers: a valid token activates the owner and the new password really
logs in; unknown, expired, and already-consumed tokens are asserted to
produce a byte-identical response (status + body) -- the amendment's
core requirement, verified at the HTTP layer, not just at the use-case
layer (see test_activate_owner.py for that).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import text

from restaurant_os_api.main import create_app
from restaurant_os_api.modules.identity.application.services import TenantProvisioningService
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyFeatureFlagRepository,
    SQLAlchemyOwnerActivationTokenRepository,
    SQLAlchemyRolePermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemySubscriptionRepository,
    SQLAlchemyTenantDirectoryRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
    SQLAlchemyUserRoleRepository,
)
from restaurant_os_api.modules.identity.infrastructure.security import JWTTokenService
from restaurant_os_api.modules.identity.presentation.dependencies import (
    get_session_factory,
    get_token_service,
)
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter


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


async def _provision(
    session_factory, token_service: JWTTokenService, *, legal_name: str, email: str
):
    service = TenantProvisioningService(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        subscription_repository_factory=SQLAlchemySubscriptionRepository,
        feature_flag_repository_factory=SQLAlchemyFeatureFlagRepository,
        directory_repository_factory=SQLAlchemyTenantDirectoryRepository,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
        user_repository_factory=SQLAlchemyUserRepository,
        user_role_repository_factory=SQLAlchemyUserRoleRepository,
        owner_activation_token_repository_factory=SQLAlchemyOwnerActivationTokenRepository,
        token_service=token_service,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )
    return await service.provision(
        legal_name=legal_name,
        display_name=legal_name,
        default_currency_code="USD",
        owner_email=email,
    )


async def test_a_valid_token_activates_and_the_new_password_logs_in(
    client: TestClient, session_factory, token_service: JWTTokenService
) -> None:
    tenant, _owner, raw_token = await _provision(
        session_factory,
        token_service,
        legal_name="Activation Flow LLC",
        email="activation-owner@example.com",
    )

    response = client.post(
        "/api/v1/owner-activation", json={"token": raw_token, "newPassword": "a brand new password"}
    )
    assert response.status_code == 200, response.text

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "tenantId": tenant.id,
            "email": "activation-owner@example.com",
            "password": "a brand new password",
        },
    )
    assert login_response.status_code == 200, login_response.text


async def test_unknown_expired_and_consumed_tokens_are_byte_identical(
    client: TestClient, session_factory, token_service: JWTTokenService
) -> None:
    _tenant, _owner, valid_but_will_expire = await _provision(
        session_factory,
        token_service,
        legal_name="Expiry Test LLC",
        email="expiry-owner@example.com",
    )
    _tenant2, _owner2, will_be_consumed = await _provision(
        session_factory,
        token_service,
        legal_name="Consumed Test LLC",
        email="consumed-owner@example.com",
    )

    # Force the first token into the past directly -- no HTTP path
    # exists to do this, and it shouldn't need one.
    token_hash = token_service.hash_refresh_token(valid_but_will_expire)
    async with session_factory() as session:
        await session.execute(
            text("UPDATE owner_activation_tokens SET expires_at = :past WHERE token_hash = :hash"),
            {"past": datetime.now(UTC) - timedelta(hours=1), "hash": token_hash},
        )
        await session.commit()

    # Consume the second token for real, once, through the real endpoint.
    first_use = client.post(
        "/api/v1/owner-activation",
        json={"token": will_be_consumed, "newPassword": "consumed once already"},
    )
    assert first_use.status_code == 200, first_use.text

    unknown_response = client.post(
        "/api/v1/owner-activation",
        json={"token": "never-issued-token", "newPassword": "irrelevant1"},
    )
    expired_response = client.post(
        "/api/v1/owner-activation",
        json={"token": valid_but_will_expire, "newPassword": "irrelevant2"},
    )
    consumed_response = client.post(
        "/api/v1/owner-activation", json={"token": will_be_consumed, "newPassword": "irrelevant3"}
    )

    responses = [unknown_response, expired_response, consumed_response]
    statuses = {r.status_code for r in responses}
    bodies = {r.text for r in responses}

    assert statuses == {401}, [r.status_code for r in responses]
    assert len(bodies) == 1, "unknown/expired/consumed must be byte-identical responses"


async def test_requires_a_new_password_of_minimum_length(client: TestClient) -> None:
    response = client.post(
        "/api/v1/owner-activation", json={"token": "whatever", "newPassword": "short"}
    )
    assert response.status_code == 422
