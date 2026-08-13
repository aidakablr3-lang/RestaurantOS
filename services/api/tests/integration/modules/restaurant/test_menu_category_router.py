"""End-to-end HTTP tests for MenuCategory CRUD against a real
PostgreSQL instance (Sprint 5 Step 4.8).

Follows test_restaurant_router.py's exact pattern (tenant-wide
authorization, no branch dimension) combined with
test_table_zone_router.py's nested-under-parent scoping discipline
(here, restaurant_id rather than branch_id).
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
    """A user holding menu.read/menu.manage/restaurant.manage tenant-wide."""
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
    body = {"name": "Appetizers"}
    body.update(overrides)
    return body


def _create_menu_category(client: TestClient, owner: dict, restaurant_id: str, **overrides) -> dict:
    response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu-categories",
        headers=_auth_headers(owner["token"]),
        json=_create_body(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestCreateMenuCategory:
    def test_a_manage_holder_can_create_a_menu_category(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(owner["token"]),
            json=_create_body(display_order=2),
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["name"] == "Appetizers"
        assert data["displayOrder"] == 2
        assert data["restaurantId"] == restaurant_id
        assert data["tenantId"] == owner["tenant_id"]

    def test_defaults_display_order_to_zero(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        data = _create_menu_category(client, owner, restaurant_id)
        assert data["displayOrder"] == 0

    def test_an_unknown_restaurant_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            f"/api/v1/restaurants/{'0' * 26}/menu-categories",
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
            f"/api/v1/restaurants/{other_restaurant['id']}/menu-categories",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESTAURANT_NOT_FOUND"

    def test_a_duplicate_name_under_the_same_restaurant_is_a_conflict(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        _create_menu_category(client, owner, restaurant_id, name="Appetizers")

        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Appetizers"),
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "MENU_CATEGORY_NAME_CONFLICT"

    async def test_the_same_name_under_a_different_restaurant_is_allowed(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        restaurant_a = await _create_restaurant(session_factory, owner["tenant_id"], name="A")
        restaurant_b = await _create_restaurant(session_factory, owner["tenant_id"], name="B")

        response_a = client.post(
            f"/api/v1/restaurants/{restaurant_a}/menu-categories",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Mains"),
        )
        response_b = client.post(
            f"/api/v1/restaurants/{restaurant_b}/menu-categories",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Mains"),
        )
        assert response_a.status_code == 201, response_a.text
        assert response_b.status_code == 201, response_b.text

    def test_requires_authentication(self, client: TestClient, restaurant_id: str) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories", json=_create_body()
        )
        assert response.status_code == 401

    def test_denied_without_menu_manage(
        self, client: TestClient, reader_only: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(reader_only["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(no_permission["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    async def test_denied_when_the_only_grant_is_on_an_inactive_role(
        self, client: TestClient, owner: dict, restaurant_id: str, session_factory
    ) -> None:
        email = "inactive@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"menu.read", "menu.manage"}),
            is_active=False,
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(token),
            json=_create_body(),
        )
        assert response.status_code == 403

    async def test_denied_once_the_grant_is_revoked(
        self, client: TestClient, owner: dict, restaurant_id: str, session_factory
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
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(token),
            json=_create_body(name="First"),
        )
        assert first.status_code == 201, first.text

        await _revoke_role(session_factory, tenant_id=owner["tenant_id"], user_role_id=user_role_id)

        second = client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(token),
            json=_create_body(name="Second"),
        )
        assert second.status_code == 403

    def test_missing_required_field_is_rejected(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(owner["token"]),
            json={},
        )
        assert response.status_code == 422

    def test_an_empty_name_is_rejected(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name=""),
        )
        assert response.status_code == 422


class TestCreateMenuCategoryIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/restaurants/{restaurant_id}/menu-categories"

        first = client.post(url, headers=headers, json=_create_body())
        second = client.post(url, headers=headers, json=_create_body())

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()

        list_response = client.get(url, headers=_auth_headers(owner["token"]))
        assert list_response.json()["meta"]["total"] == 1

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/restaurants/{restaurant_id}/menu-categories"

        first = client.post(url, headers=headers, json=_create_body(name="First"))
        assert first.status_code == 201, first.text

        second = client.post(url, headers=headers, json=_create_body(name="Second"))
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestGetMenuCategory:
    def test_a_read_holder_can_get_a_menu_category(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        menu_category = _create_menu_category(client, owner, restaurant_id)

        response = client.get(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories/{menu_category['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] == menu_category["id"]

    def test_an_unknown_id_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.get(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MENU_CATEGORY_NOT_FOUND"

    async def test_a_category_belonging_to_a_different_restaurant_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str, session_factory
    ) -> None:
        other_restaurant_id = await _create_restaurant(
            session_factory, owner["tenant_id"], name="Other"
        )
        other_category = _create_menu_category(client, owner, other_restaurant_id)

        response = client.get(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories/{other_category['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MENU_CATEGORY_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, restaurant_id: str) -> None:
        response = client.get(f"/api/v1/restaurants/{restaurant_id}/menu-categories/{'0' * 26}")
        assert response.status_code == 401

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, restaurant_id: str
    ) -> None:
        response = client.get(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories/{'0' * 26}",
            headers=_auth_headers(no_permission["token"]),
        )
        assert response.status_code == 403


class TestListMenuCategories:
    def test_lists_only_the_requested_restaurants_categories(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        for name in ("A", "B", "C"):
            _create_menu_category(client, owner, restaurant_id, name=name)

        response = client.get(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 3

    def test_pagination_offset_and_limit(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        for i in range(5):
            _create_menu_category(client, owner, restaurant_id, name=f"C{i}")

        url = f"/api/v1/restaurants/{restaurant_id}/menu-categories"
        page_1 = client.get(f"{url}?offset=0&limit=2", headers=_auth_headers(owner["token"]))
        page_2 = client.get(f"{url}?offset=2&limit=2", headers=_auth_headers(owner["token"]))

        assert page_1.status_code == page_2.status_code == 200
        assert len(page_1.json()["data"]) == 2
        assert len(page_2.json()["data"]) == 2
        assert page_1.json()["meta"]["total"] == 5
        ids_page_1 = {c["id"] for c in page_1.json()["data"]}
        ids_page_2 = {c["id"] for c in page_2.json()["data"]}
        assert ids_page_1.isdisjoint(ids_page_2)

    def test_an_unknown_restaurant_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(
            f"/api/v1/restaurants/{'0' * 26}/menu-categories",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESTAURANT_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, restaurant_id: str) -> None:
        response = client.get(f"/api/v1/restaurants/{restaurant_id}/menu-categories")
        assert response.status_code == 401

    def test_reader_only_can_list(
        self, client: TestClient, reader_only: dict, restaurant_id: str
    ) -> None:
        response = client.get(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(reader_only["token"]),
        )
        assert response.status_code == 200

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, restaurant_id: str
    ) -> None:
        response = client.get(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories",
            headers=_auth_headers(no_permission["token"]),
        )
        assert response.status_code == 403


class TestUpdateMenuCategory:
    def test_a_manage_holder_can_update_a_menu_category(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        menu_category = _create_menu_category(client, owner, restaurant_id)

        response = client.patch(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories/{menu_category['id']}",
            headers=_auth_headers(owner["token"]),
            json={"name": "Renamed", "displayOrder": 9},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["name"] == "Renamed"
        assert data["displayOrder"] == 9
        assert data["id"] == menu_category["id"]
        assert data["restaurantId"] == restaurant_id

    def test_updating_an_unknown_id_returns_404(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        response = client.patch(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404

    async def test_updating_a_category_via_a_different_restaurants_url_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str, session_factory
    ) -> None:
        other_restaurant_id = await _create_restaurant(
            session_factory, owner["tenant_id"], name="Other"
        )
        menu_category = _create_menu_category(client, owner, restaurant_id)

        response = client.patch(
            f"/api/v1/restaurants/{other_restaurant_id}/menu-categories/{menu_category['id']}",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Hijacked"),
        )
        assert response.status_code == 404

    def test_renaming_to_a_sibling_categorys_name_is_a_conflict(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        _create_menu_category(client, owner, restaurant_id, name="Existing")
        to_rename = _create_menu_category(client, owner, restaurant_id, name="ToRename")

        response = client.patch(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories/{to_rename['id']}",
            headers=_auth_headers(owner["token"]),
            json=_create_body(name="Existing"),
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "MENU_CATEGORY_NAME_CONFLICT"

    def test_denied_without_menu_manage(
        self, client: TestClient, owner: dict, reader_only: dict, restaurant_id: str
    ) -> None:
        menu_category = _create_menu_category(client, owner, restaurant_id)

        response = client.patch(
            f"/api/v1/restaurants/{restaurant_id}/menu-categories/{menu_category['id']}",
            headers=_auth_headers(reader_only["token"]),
            json=_create_body(name="Hijacked"),
        )
        assert response.status_code == 403

    def test_idempotent_update_replays_on_the_same_key_and_body(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        menu_category = _create_menu_category(client, owner, restaurant_id)
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        body = _create_body(name="Renamed Once")

        url = f"/api/v1/restaurants/{restaurant_id}/menu-categories/{menu_category['id']}"
        first = client.patch(url, headers=headers, json=body)
        second = client.patch(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_idempotency_key_conflict_on_a_different_body(
        self, client: TestClient, owner: dict, restaurant_id: str
    ) -> None:
        menu_category = _create_menu_category(client, owner, restaurant_id)
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/restaurants/{restaurant_id}/menu-categories/{menu_category['id']}"

        first = client.patch(url, headers=headers, json=_create_body(name="Name One"))
        assert first.status_code == 200, first.text

        second = client.patch(url, headers=headers, json=_create_body(name="Name Two"))
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
