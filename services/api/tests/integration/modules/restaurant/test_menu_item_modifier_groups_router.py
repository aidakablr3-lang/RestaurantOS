"""End-to-end HTTP tests for the MenuItem<->ModifierGroup attachment
endpoint (``PUT /api/v1/menu-items/{id}/modifier-groups``) against a
real PostgreSQL instance (Sprint 5 Step 4.9).

Covers atomic full-set replace semantics, cross-tenant isolation for
both the menu item and every referenced modifier group, RBAC,
idempotency, and the underlying ``menu_item_modifier_groups`` unique
constraint / RLS.
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
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyMenuItemModifierGroupRepository,
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
    session_factory, *, tenant_id: str, user_id: str, permission_codes: frozenset[str]
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
                is_active=True,
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
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        permission_codes=frozenset({"menu.read", "menu.manage", "restaurant.manage"}),
    )
    token = _login_sync(client, tenant_id=tenant_id, email=email)
    yield {"tenant_id": tenant_id, "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def restaurant_id(session_factory, owner: dict) -> str:
    return await _create_restaurant(session_factory, owner["tenant_id"])


@pytest_asyncio.fixture
async def menu_category(client: TestClient, owner: dict, restaurant_id: str) -> dict:
    response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu-categories",
        headers=_auth_headers(owner["token"]),
        json={"name": "Mains"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest_asyncio.fixture
async def menu_item(client: TestClient, owner: dict, menu_category: dict) -> dict:
    response = client.post(
        f"/api/v1/menu-categories/{menu_category['id']}/menu-items",
        headers=_auth_headers(owner["token"]),
        json={"name": "Burger", "priceAmount": "9.99", "currencyCode": "USD"},
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


def _create_modifier_group(client: TestClient, owner: dict, name: str = "Size") -> dict:
    response = client.post(
        "/api/v1/modifier-groups",
        headers=_auth_headers(owner["token"]),
        json={"name": name, "selectionType": "single"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestReplaceMenuItemModifierGroups:
    def test_attaches_a_set_of_groups(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        group_a = _create_modifier_group(client, owner, "Size")
        group_b = _create_modifier_group(client, owner, "Spice")

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/modifier-groups",
            headers=_auth_headers(owner["token"]),
            json={"modifierGroupIds": [group_a["id"], group_b["id"]]},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["menuItemId"] == menu_item["id"]
        assert set(data["modifierGroupIds"]) == {group_a["id"], group_b["id"]}

    def test_replace_is_atomic_not_additive(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        """[group-A, group-B, group-C] replaced with [group-A, group-D]
        must result in exactly [group-A, group-D] -- group-B and
        group-C must be gone, not retained alongside the new set."""
        group_a = _create_modifier_group(client, owner, "A")
        group_b = _create_modifier_group(client, owner, "B")
        group_c = _create_modifier_group(client, owner, "C")
        group_d = _create_modifier_group(client, owner, "D")
        url = f"/api/v1/menu-items/{menu_item['id']}/modifier-groups"

        first = client.put(
            url,
            headers=_auth_headers(owner["token"]),
            json={"modifierGroupIds": [group_a["id"], group_b["id"], group_c["id"]]},
        )
        assert first.status_code == 200, first.text
        assert set(first.json()["data"]["modifierGroupIds"]) == {
            group_a["id"],
            group_b["id"],
            group_c["id"],
        }

        second = client.put(
            url,
            headers=_auth_headers(owner["token"]),
            json={"modifierGroupIds": [group_a["id"], group_d["id"]]},
        )
        assert second.status_code == 200, second.text
        assert set(second.json()["data"]["modifierGroupIds"]) == {group_a["id"], group_d["id"]}

    def test_an_empty_set_clears_every_attachment(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        group_a = _create_modifier_group(client, owner, "A")
        url = f"/api/v1/menu-items/{menu_item['id']}/modifier-groups"

        client.put(
            url, headers=_auth_headers(owner["token"]), json={"modifierGroupIds": [group_a["id"]]}
        )

        response = client.put(
            url, headers=_auth_headers(owner["token"]), json={"modifierGroupIds": []}
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["modifierGroupIds"] == []

    def test_duplicate_ids_in_the_request_collapse_to_one(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        group_a = _create_modifier_group(client, owner, "A")

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/modifier-groups",
            headers=_auth_headers(owner["token"]),
            json={"modifierGroupIds": [group_a["id"], group_a["id"]]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["modifierGroupIds"] == [group_a["id"]]

    def test_an_unknown_menu_item_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.put(
            f"/api/v1/menu-items/{'0' * 26}/modifier-groups",
            headers=_auth_headers(owner["token"]),
            json={"modifierGroupIds": []},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MENU_ITEM_NOT_FOUND"

    async def test_an_unknown_modifier_group_id_is_404_and_not_partially_applied(
        self, client: TestClient, owner: dict, menu_item: dict, session_factory
    ) -> None:
        group_a = _create_modifier_group(client, owner, "A")
        url = f"/api/v1/menu-items/{menu_item['id']}/modifier-groups"

        # Pre-existing attachment that must survive the failed call.
        setup = client.put(
            url, headers=_auth_headers(owner["token"]), json={"modifierGroupIds": [group_a["id"]]}
        )
        assert setup.status_code == 200, setup.text

        response = client.put(
            url,
            headers=_auth_headers(owner["token"]),
            json={"modifierGroupIds": [group_a["id"], "0" * 26]},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MODIFIER_GROUP_NOT_FOUND"

        # Verify no partial replace happened by inspecting the join
        # table directly -- there is no GET endpoint for the current
        # attachment set in this step's approved scope.
        async with UnitOfWork(session_factory, TenantContext(owner["tenant_id"])) as uow:
            stored = await SQLAlchemyMenuItemModifierGroupRepository(
                uow.session
            ).list_modifier_group_ids_for_menu_item(owner["tenant_id"], menu_item["id"])
        assert stored == frozenset({group_a["id"]})

    async def test_a_menu_item_belonging_to_another_tenant_is_404_not_a_leak(
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
            permission_codes=frozenset({"menu.manage", "restaurant.manage"}),
        )
        other_token = _login_sync(client, tenant_id=other_tenant_id, email=other_email)
        other_restaurant = client.post(
            "/api/v1/restaurants",
            headers=_auth_headers(other_token),
            json={"legalName": "Other", "displayName": "Other", "defaultCurrencyCode": "USD"},
        ).json()["data"]
        other_category = client.post(
            f"/api/v1/restaurants/{other_restaurant['id']}/menu-categories",
            headers=_auth_headers(other_token),
            json={"name": "Other"},
        ).json()["data"]
        other_item = client.post(
            f"/api/v1/menu-categories/{other_category['id']}/menu-items",
            headers=_auth_headers(other_token),
            json={"name": "Other Item", "priceAmount": "1.00", "currencyCode": "USD"},
        ).json()["data"]

        response = client.put(
            f"/api/v1/menu-items/{other_item['id']}/modifier-groups",
            headers=_auth_headers(owner["token"]),
            json={"modifierGroupIds": []},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MENU_ITEM_NOT_FOUND"

    async def test_a_modifier_group_belonging_to_another_tenant_is_404_not_a_leak(
        self, client: TestClient, owner: dict, menu_item: dict, session_factory
    ) -> None:
        other_tenant_id = generate_ulid()
        other_email = "othergroup@example.com"
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

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/modifier-groups",
            headers=_auth_headers(owner["token"]),
            json={"modifierGroupIds": [other_group["id"]]},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MODIFIER_GROUP_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, menu_item: dict) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/modifier-groups",
            json={"modifierGroupIds": []},
        )
        assert response.status_code == 401

    def test_denied_without_menu_manage(
        self, client: TestClient, reader_only: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/modifier-groups",
            headers=_auth_headers(reader_only["token"]),
            json={"modifierGroupIds": []},
        )
        assert response.status_code == 403


class TestReplaceMenuItemModifierGroupsIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        group_a = _create_modifier_group(client, owner, "A")
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/menu-items/{menu_item['id']}/modifier-groups"
        body = {"modifierGroupIds": [group_a["id"]]}

        first = client.put(url, headers=headers, json=body)
        second = client.put(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        group_a = _create_modifier_group(client, owner, "A")
        group_b = _create_modifier_group(client, owner, "B")
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/menu-items/{menu_item['id']}/modifier-groups"

        first = client.put(url, headers=headers, json={"modifierGroupIds": [group_a["id"]]})
        assert first.status_code == 200, first.text

        second = client.put(url, headers=headers, json={"modifierGroupIds": [group_b["id"]]})
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
