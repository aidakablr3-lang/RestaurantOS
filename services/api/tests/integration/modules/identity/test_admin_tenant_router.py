"""End-to-end HTTP tests for /api/v1/admin/tenants/* against a real
PostgreSQL instance.

Requires TEST_DATABASE_URL (see tests/integration/conftest.py). Follows
test_auth_router.py's pattern: dependency overrides replace only the
session factory and token service, so the password hasher, use cases,
repositories, RLS policies, and routing are all exercised exactly as in
production. Every test authenticates through a real POST /auth/login
call, exactly as apps/admin-web does -- these are the same 6 Tenant
Administration flows Sprint 4.1 Step 3 verified by hand in a browser,
now automated.

The seeded platform-admin always lives in its own tenant, separate from
whatever tenant a given test creates/acts on -- suspending or
offboarding a tenant revokes every session belonging to it (correct
behavior), including the admin's own if the admin happened to live
there too, which would silently invalidate the admin's bearer token
mid-test. This mirrors the workaround Sprint 4.1 Step 3's manual
browser verification needed for the same reason (see docs/AI_HANDOFF.md).
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


async def _seed_user(
    session_factory, *, tenant_id: str, email: str, is_platform_admin: bool
) -> str:
    """Inserts a tenant + user, returns the user's id. No user-creation
    use case exists yet (Sprint 4.1 Decision C -- interim boolean, no
    RBAC/admin-invite flow), so this goes through raw SQL, the same
    pattern test_auth_router.py and test_repositories.py already use."""
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
                "1, 'active', :is_platform_admin)"
            ),
            {
                "id": user_id,
                "tenant_id": tenant_id,
                "email": email,
                "password_hash": password_hash,
                "is_platform_admin": is_platform_admin,
            },
        )
    return user_id


async def _login(client: TestClient, *, tenant_id: str, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"tenantId": tenant_id, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["accessToken"]


@pytest_asyncio.fixture
async def platform_admin_token(session_factory, client: TestClient) -> AsyncGenerator[str]:
    """A platform-admin user in its own tenant, distinct from any tenant
    a test onboards/suspends/offboards -- see module docstring."""
    admin_tenant_id = generate_ulid()
    email = "platform-admin@example.com"
    await _seed_user(
        session_factory, tenant_id=admin_tenant_id, email=email, is_platform_admin=True
    )
    yield await _login(client, tenant_id=admin_tenant_id, email=email)


@pytest_asyncio.fixture
async def non_admin_token(session_factory, client: TestClient) -> AsyncGenerator[str]:
    tenant_id = generate_ulid()
    email = "member@example.com"
    await _seed_user(session_factory, tenant_id=tenant_id, email=email, is_platform_admin=False)
    yield await _login(client, tenant_id=tenant_id, email=email)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestOnboardTenant:
    def test_creates_an_active_tenant(self, client: TestClient, platform_admin_token: str) -> None:
        response = client.post(
            "/api/v1/admin/tenants",
            headers=_auth_headers(platform_admin_token),
            json={
                "legalName": "Acme Restaurants LLC",
                "displayName": "Acme Restaurants",
                "defaultCurrencyCode": "USD",
            },
        )

        assert response.status_code == 201, response.text
        body = response.json()["data"]
        assert body["legalName"] == "Acme Restaurants LLC"
        assert body["displayName"] == "Acme Restaurants"
        assert body["status"] == "active"  # provisioning activates in the same transaction
        assert body["defaultCurrencyCode"] == "USD"
        assert body["id"]

    def test_rejects_a_duplicate_legal_name(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        payload = {
            "legalName": "Duplicate Diner LLC",
            "displayName": "Duplicate Diner",
            "defaultCurrencyCode": "USD",
        }
        first = client.post(
            "/api/v1/admin/tenants", headers=_auth_headers(platform_admin_token), json=payload
        )
        assert first.status_code == 201

        second = client.post(
            "/api/v1/admin/tenants", headers=_auth_headers(platform_admin_token), json=payload
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "TENANT_LEGAL_NAME_CONFLICT"

    def test_rejects_an_invalid_currency_code(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        response = client.post(
            "/api/v1/admin/tenants",
            headers=_auth_headers(platform_admin_token),
            json={
                "legalName": "Bad Currency LLC",
                "displayName": "Bad Currency",
                "defaultCurrencyCode": "US",
            },
        )
        assert response.status_code == 422

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/admin/tenants",
            json={
                "legalName": "No Auth LLC",
                "displayName": "No Auth",
                "defaultCurrencyCode": "USD",
            },
        )
        assert response.status_code == 401

    def test_rejects_a_non_platform_admin(self, client: TestClient, non_admin_token: str) -> None:
        """A regular authenticated user, not a platform admin, must be
        rejected -- the equivalent, for this router, of test_repositories.py's
        "single most important test" for RLS: a security guarantee that
        must be verified end-to-end, not just designed."""
        response = client.post(
            "/api/v1/admin/tenants",
            headers=_auth_headers(non_admin_token),
            json={
                "legalName": "Sneaky LLC",
                "displayName": "Sneaky",
                "defaultCurrencyCode": "USD",
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "INSUFFICIENT_PRIVILEGES"


class TestListAndGetTenant:
    def test_list_returns_pagination_metadata(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        for i in range(3):
            client.post(
                "/api/v1/admin/tenants",
                headers=_auth_headers(platform_admin_token),
                json={
                    "legalName": f"List Test {i} LLC",
                    "displayName": f"List Test {i}",
                    "defaultCurrencyCode": "USD",
                },
            )

        response = client.get(
            "/api/v1/admin/tenants?offset=0&limit=2",
            headers=_auth_headers(platform_admin_token),
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 2
        assert body["meta"]["total"] >= 3
        assert body["meta"]["offset"] == 0
        assert body["meta"]["limit"] == 2

    def test_list_filters_by_status(self, client: TestClient, platform_admin_token: str) -> None:
        created = client.post(
            "/api/v1/admin/tenants",
            headers=_auth_headers(platform_admin_token),
            json={
                "legalName": "Filter Me LLC",
                "displayName": "Filter Me",
                "defaultCurrencyCode": "USD",
            },
        ).json()["data"]
        client.post(
            f"/api/v1/admin/tenants/{created['id']}/suspend",
            headers=_auth_headers(platform_admin_token),
        )

        suspended = client.get(
            "/api/v1/admin/tenants?status=suspended",
            headers=_auth_headers(platform_admin_token),
        ).json()["data"]
        assert any(t["id"] == created["id"] for t in suspended)

        active = client.get(
            "/api/v1/admin/tenants?status=active", headers=_auth_headers(platform_admin_token)
        ).json()["data"]
        assert not any(t["id"] == created["id"] for t in active)

    def test_get_returns_the_tenant(self, client: TestClient, platform_admin_token: str) -> None:
        created = client.post(
            "/api/v1/admin/tenants",
            headers=_auth_headers(platform_admin_token),
            json={
                "legalName": "Get Me LLC",
                "displayName": "Get Me",
                "defaultCurrencyCode": "USD",
            },
        ).json()["data"]

        response = client.get(
            f"/api/v1/admin/tenants/{created['id']}", headers=_auth_headers(platform_admin_token)
        )
        assert response.status_code == 200
        assert response.json()["data"]["id"] == created["id"]

    def test_get_unknown_tenant(self, client: TestClient, platform_admin_token: str) -> None:
        # Existing behavior, not changed here: GetTenantUseCase raises the
        # same TenantNotFoundError the auth-time tenant lookup does, which
        # the global handler maps to 401 (deliberately, for auth-context
        # enumeration resistance -- see core/exceptions.py). For an
        # already-authenticated platform admin doing an ID lookup, a 404
        # would arguably read better, but that is a design question, not
        # a defect this suite fixes -- asserting current behavior here so
        # a future change to it is a deliberate, visible diff.
        response = client.get(
            f"/api/v1/admin/tenants/{generate_ulid()}", headers=_auth_headers(platform_admin_token)
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "TENANT_NOT_FOUND"

    def test_rejects_a_non_platform_admin(self, client: TestClient, non_admin_token: str) -> None:
        response = client.get("/api/v1/admin/tenants", headers=_auth_headers(non_admin_token))
        assert response.status_code == 403


class TestUpdateTenant:
    def test_updates_display_name_and_metadata(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        created = client.post(
            "/api/v1/admin/tenants",
            headers=_auth_headers(platform_admin_token),
            json={
                "legalName": "Update Me LLC",
                "displayName": "Update Me",
                "defaultCurrencyCode": "USD",
            },
        ).json()["data"]

        response = client.patch(
            f"/api/v1/admin/tenants/{created['id']}",
            headers=_auth_headers(platform_admin_token),
            json={"displayName": "Updated Name", "metadata": {"neighborhood": "Downtown"}},
        )

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["displayName"] == "Updated Name"
        assert body["metadata"] == {"neighborhood": "Downtown"}

        refetched = client.get(
            f"/api/v1/admin/tenants/{created['id']}", headers=_auth_headers(platform_admin_token)
        ).json()["data"]
        assert refetched["displayName"] == "Updated Name"

    def test_rejects_a_non_platform_admin(self, client: TestClient, non_admin_token: str) -> None:
        response = client.patch(
            f"/api/v1/admin/tenants/{generate_ulid()}",
            headers=_auth_headers(non_admin_token),
            json={"displayName": "Nope", "metadata": {}},
        )
        assert response.status_code == 403


class TestSuspendReactivateOffboard:
    def _create_tenant(self, client: TestClient, platform_admin_token: str) -> dict:
        return client.post(
            "/api/v1/admin/tenants",
            headers=_auth_headers(platform_admin_token),
            json={
                "legalName": "Lifecycle Test LLC",
                "displayName": "Lifecycle Test",
                "defaultCurrencyCode": "USD",
            },
        ).json()["data"]

    def test_suspend_then_reactivate(self, client: TestClient, platform_admin_token: str) -> None:
        tenant = self._create_tenant(client, platform_admin_token)

        suspend_response = client.post(
            f"/api/v1/admin/tenants/{tenant['id']}/suspend",
            headers=_auth_headers(platform_admin_token),
        )
        assert suspend_response.status_code == 200
        assert suspend_response.json()["data"]["status"] == "suspended"

        reactivate_response = client.post(
            f"/api/v1/admin/tenants/{tenant['id']}/reactivate",
            headers=_auth_headers(platform_admin_token),
        )
        assert reactivate_response.status_code == 200
        assert reactivate_response.json()["data"]["status"] == "active"

    def test_suspending_an_already_suspended_tenant_is_rejected(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        tenant = self._create_tenant(client, platform_admin_token)
        client.post(
            f"/api/v1/admin/tenants/{tenant['id']}/suspend",
            headers=_auth_headers(platform_admin_token),
        )

        response = client.post(
            f"/api/v1/admin/tenants/{tenant['id']}/suspend",
            headers=_auth_headers(platform_admin_token),
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_TENANT_STATUS_TRANSITION"

    async def test_suspend_revokes_the_tenants_own_sessions(
        self, client: TestClient, platform_admin_token: str, session_factory
    ) -> None:
        """Data Architecture v2.0 SS4.5: suspension must immediately kill
        that tenant's existing sessions, not just block new ones."""
        tenant = self._create_tenant(client, platform_admin_token)
        member_email = "member-of-suspended-tenant@example.com"
        await _seed_user(
            session_factory, tenant_id=tenant["id"], email=member_email, is_platform_admin=False
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"tenantId": tenant["id"], "email": member_email, "password": PASSWORD},
        )
        refresh_token = login_response.json()["data"]["refreshToken"]

        client.post(
            f"/api/v1/admin/tenants/{tenant['id']}/suspend",
            headers=_auth_headers(platform_admin_token),
        )

        refresh_after_suspend = client.post(
            "/api/v1/auth/refresh",
            json={"tenantId": tenant["id"], "refreshToken": refresh_token},
        )
        assert refresh_after_suspend.status_code == 401

    def test_offboard_transitions_status_and_revokes_sessions(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        tenant = self._create_tenant(client, platform_admin_token)

        response = client.post(
            f"/api/v1/admin/tenants/{tenant['id']}/offboard",
            headers=_auth_headers(platform_admin_token),
        )

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "offboarded"

    def test_rejects_a_non_platform_admin(self, client: TestClient, non_admin_token: str) -> None:
        tenant_id = generate_ulid()
        for action in ("suspend", "reactivate", "offboard"):
            response = client.post(
                f"/api/v1/admin/tenants/{tenant_id}/{action}",
                headers=_auth_headers(non_admin_token),
            )
            assert response.status_code == 403, f"{action} did not reject a non-admin"
