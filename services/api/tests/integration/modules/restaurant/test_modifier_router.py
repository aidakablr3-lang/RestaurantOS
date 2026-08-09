"""End-to-end HTTP tests for Modifier CRUD against a real PostgreSQL
instance (Sprint 5 Step 4.9).

Follows test_modifier_group_router.py's exact pattern, nested one
level deeper under modifier_group_id.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime
from decimal import Decimal

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
) -> str:
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
        user_role = await user_role_repo.create(
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
    return user_role.id


async def _revoke_role(session_factory, *, tenant_id: str, user_role_id: str) -> None:
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await SQLAlchemyUserRoleRepository(uow.session).revoke(tenant_id, user_role_id)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def owner(session_factory, client: TestClient) -> AsyncGenerator[dict]:
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        permission_codes=frozenset({"menu.read", "menu.manage"}),
    )
    token = _login_sync(client, tenant_id=tenant_id, email=email)
    yield {"tenant_id": tenant_id, "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def modifier_group(client: TestClient, owner: dict) -> dict:
    response = client.post(
        "/api/v1/modifier-groups",
        headers=_auth_headers(owner["token"]),
        json={"name": "Size", "selectionType": "single"},
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
        permission_codes=frozenset({"menu.read"}),
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
    body = {"name": "Large", "priceDelta": "1.50"}
    body.update(overrides)
    return body


def _create_modifier(client: TestClient, owner: dict, modifier_group_id: str, **overrides) -> dict:
    response = client.post(
        f"/api/v1/modifier-groups/{modifier_group_id}/modifiers",
        headers=_auth_headers(owner["token"]),
        json=_create_body(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestCreateModifier:
    def test_a_manage_holder_can_create_a_modifier(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        response = client.post(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["name"] == "Large"
        assert Decimal(data["priceDelta"]) == Decimal("1.50")
        assert data["modifierGroupId"] == modifier_group["id"]
        assert data["tenantId"] == owner["tenant_id"]

    def test_price_delta_may_be_negative(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        data = _create_modifier(client, owner, modifier_group["id"], priceDelta="-0.50")
        assert Decimal(data["priceDelta"]) == Decimal("-0.50")

    def test_defaults_price_delta_to_zero(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        response = client.post(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(owner["token"]),
            json={"name": "Plain"},
        )
        assert response.status_code == 201, response.text
        assert Decimal(response.json()["data"]["priceDelta"]) == Decimal(0)

    def test_an_unknown_modifier_group_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            f"/api/v1/modifier-groups/{'0' * 26}/modifiers",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MODIFIER_GROUP_NOT_FOUND"

    async def test_a_group_belonging_to_another_tenant_is_404_not_a_leak(
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
            permission_codes=frozenset({"menu.manage"}),
        )
        other_token = _login_sync(client, tenant_id=other_tenant_id, email=other_email)
        other_group = client.post(
            "/api/v1/modifier-groups",
            headers=_auth_headers(other_token),
            json={"name": "Other", "selectionType": "single"},
        ).json()["data"]

        response = client.post(
            f"/api/v1/modifier-groups/{other_group['id']}/modifiers",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MODIFIER_GROUP_NOT_FOUND"

    def test_duplicate_names_within_the_same_group_are_allowed(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        _create_modifier(client, owner, modifier_group["id"], name="Large")
        response = client.post(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Large"),
        )
        assert response.status_code == 201, response.text

    def test_requires_authentication(self, client: TestClient, modifier_group: dict) -> None:
        response = client.post(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers", json=_create_body()
        )
        assert response.status_code == 401

    def test_denied_without_menu_manage(
        self, client: TestClient, reader_only: dict, modifier_group: dict
    ) -> None:
        response = client.post(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(reader_only["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, modifier_group: dict
    ) -> None:
        response = client.post(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(no_permission["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    async def test_denied_once_the_grant_is_revoked(
        self, client: TestClient, owner: dict, modifier_group: dict, session_factory
    ) -> None:
        email = "revoked@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        user_role_id = await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"menu.read", "menu.manage"}),
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
        first = client.post(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(token),
            json=_create_body(name="First"),
        )
        assert first.status_code == 201, first.text

        await _revoke_role(session_factory, tenant_id=owner["tenant_id"], user_role_id=user_role_id)

        second = client.post(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(token),
            json=_create_body(name="Second"),
        )
        assert second.status_code == 403

    def test_missing_required_field_is_rejected(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        response = client.post(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(owner["token"]),
            json={},
        )
        assert response.status_code == 422


class TestCreateModifierIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers"

        first = client.post(url, headers=headers, json=_create_body())
        second = client.post(url, headers=headers, json=_create_body())

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()

        list_response = client.get(url, headers=_auth_headers(owner["token"]))
        assert len(list_response.json()["data"]) == 1

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers"

        first = client.post(url, headers=headers, json=_create_body(name="First"))
        assert first.status_code == 201, first.text

        second = client.post(url, headers=headers, json=_create_body(name="Second"))
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestGetModifier:
    def test_a_read_holder_can_get_a_modifier(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        modifier = _create_modifier(client, owner, modifier_group["id"])

        response = client.get(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{modifier['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] == modifier["id"]

    def test_an_unknown_id_is_404(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        response = client.get(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MODIFIER_NOT_FOUND"

    async def test_a_modifier_belonging_to_a_different_group_is_404(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        other_group = client.post(
            "/api/v1/modifier-groups",
            headers=_auth_headers(owner["token"]),
            json={"name": "Spice", "selectionType": "single"},
        ).json()["data"]
        other_modifier = _create_modifier(client, owner, other_group["id"])

        response = client.get(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{other_modifier['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MODIFIER_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, modifier_group: dict) -> None:
        response = client.get(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{'0' * 26}"
        )
        assert response.status_code == 401

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, modifier_group: dict
    ) -> None:
        response = client.get(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{'0' * 26}",
            headers=_auth_headers(no_permission["token"]),
        )
        assert response.status_code == 403


class TestListModifiers:
    def test_lists_only_the_requested_groups_modifiers(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        for name in ("Small", "Medium", "Large"):
            _create_modifier(client, owner, modifier_group["id"], name=name)

        response = client.get(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200
        names = {m["name"] for m in response.json()["data"]}
        assert names == {"Small", "Medium", "Large"}

    def test_response_has_no_pagination_meta(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        response = client.get(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(owner["token"]),
        )
        assert response.json().get("meta") is None

    def test_an_unknown_modifier_group_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(
            f"/api/v1/modifier-groups/{'0' * 26}/modifiers", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MODIFIER_GROUP_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, modifier_group: dict) -> None:
        response = client.get(f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers")
        assert response.status_code == 401

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, modifier_group: dict
    ) -> None:
        response = client.get(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers",
            headers=_auth_headers(no_permission["token"]),
        )
        assert response.status_code == 403


class TestUpdateModifier:
    def test_a_manage_holder_can_update_a_modifier(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        modifier = _create_modifier(client, owner, modifier_group["id"])

        response = client.patch(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{modifier['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": "Extra Large", "priceDelta": "2.00"},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["name"] == "Extra Large"
        assert Decimal(data["priceDelta"]) == Decimal("2.00")

    def test_updating_an_unknown_id_returns_404(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        response = client.patch(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404

    async def test_updating_a_modifier_via_a_different_groups_url_is_404(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        other_group = client.post(
            "/api/v1/modifier-groups",
            headers=_auth_headers(owner["token"]),
            json={"name": "Spice", "selectionType": "single"},
        ).json()["data"]
        modifier = _create_modifier(client, owner, modifier_group["id"])

        response = client.patch(
            f"/api/v1/modifier-groups/{other_group['id']}/modifiers/{modifier['id']}",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Hijacked"),
        )
        assert response.status_code == 404

    def test_denied_without_menu_manage(
        self, client: TestClient, owner: dict, reader_only: dict, modifier_group: dict
    ) -> None:
        modifier = _create_modifier(client, owner, modifier_group["id"])

        response = client.patch(
            f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{modifier['id']}",
            headers=_auth_headers(reader_only["token"]),
            json=_create_body(name="Hijacked"),
        )
        assert response.status_code == 403

    def test_idempotent_update_replays_on_the_same_key_and_body(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        modifier = _create_modifier(client, owner, modifier_group["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        body = _create_body(name="Renamed Once")

        url = f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{modifier['id']}"
        first = client.patch(url, headers=headers, json=body)
        second = client.patch(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_idempotency_key_conflict_on_a_different_body(
        self, client: TestClient, owner: dict, modifier_group: dict
    ) -> None:
        modifier = _create_modifier(client, owner, modifier_group["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/modifier-groups/{modifier_group['id']}/modifiers/{modifier['id']}"

        first = client.patch(url, headers=headers, json=_create_body(name="Name One"))
        assert first.status_code == 200, first.text

        second = client.patch(url, headers=headers, json=_create_body(name="Name Two"))
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
