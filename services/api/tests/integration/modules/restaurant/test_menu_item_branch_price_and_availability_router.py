"""End-to-end HTTP tests for MenuItemBranchPrice/MenuItemAvailability
(Sprint 5 Step 4.10) against a real PostgreSQL instance.

Both routes are flat (``PUT``/``GET /api/v1/menu-items/{id}/branch-price``
and ``/availability``) -- ``branch_id`` arrives in the ``PUT`` body, not
the URL, gated by the coarse ``require_permission_at_any_scope`` plus
``resolve_and_authorize_branch``'s fine-grained check, the same shape
``test_qr_code_router.py`` already established for
``POST /api/v1/tables/{id}/qr-codes``. ``GET`` returns the full
override-row history across every branch the caller can see -- no
effective-price/effective-availability resolution algorithm exists yet
(see ``list_menu_item_branch_prices.py``'s own docstring).
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
from sqlalchemy.exc import DBAPIError

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
                default_scope=RoleScope.BRANCH if branch_id else RoleScope.TENANT,
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
                branch_id=branch_id,
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
    """A user holding menu.read/menu.manage/branch.manage/restaurant.manage tenant-wide."""
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        permission_codes=frozenset(
            {"menu.read", "menu.manage", "branch.manage", "restaurant.manage"}
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


@pytest_asyncio.fixture
async def no_permission(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    email = "noperm@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


def _set_branch_price(
    client: TestClient,
    owner: dict,
    menu_item_id: str,
    branch_id: str,
    *,
    price_amount: str = "8.50",
    effective_from: str = "2026-01-01T00:00:00Z",
    effective_to: str | None = None,
) -> dict:
    body: dict = {
        "branchId": branch_id,
        "priceAmount": price_amount,
        "effectiveFrom": effective_from,
    }
    if effective_to is not None:
        body["effectiveTo"] = effective_to
    response = client.put(
        f"/api/v1/menu-items/{menu_item_id}/branch-price",
        headers=_auth_headers(owner["token"]),
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _set_availability(
    client: TestClient,
    owner: dict,
    menu_item_id: str,
    branch_id: str,
    *,
    is_available: bool = False,
    effective_from: str = "2026-01-01T00:00:00Z",
    effective_to: str | None = None,
) -> dict:
    body: dict = {
        "branchId": branch_id,
        "isAvailable": is_available,
        "effectiveFrom": effective_from,
    }
    if effective_to is not None:
        body["effectiveTo"] = effective_to
    response = client.put(
        f"/api/v1/menu-items/{menu_item_id}/availability",
        headers=_auth_headers(owner["token"]),
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestCreateMenuItemBranchPrice:
    def test_a_manage_holder_can_set_a_branch_price(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        data = _set_branch_price(client, owner, menu_item["id"], branch["id"])
        assert data["menuItemId"] == menu_item["id"]
        assert data["branchId"] == branch["id"]
        assert data["priceAmount"] == "8.50"
        assert data["tenantId"] == owner["tenant_id"]
        assert data["effectiveTo"] is None

    def test_a_closed_window_followed_by_an_open_ended_window_both_work(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        """Non-overlapping, back-to-back windows: [Jan 1, Feb 1) then
        [Feb 1, forever) -- the second starts exactly where the first
        ends, which the half-open ``[)`` range semantics treat as
        adjacent, not overlapping."""
        closed = _set_branch_price(
            client,
            owner,
            menu_item["id"],
            branch["id"],
            effective_from="2026-01-01T00:00:00Z",
            effective_to="2026-02-01T00:00:00Z",
        )
        open_ended = _set_branch_price(
            client,
            owner,
            menu_item["id"],
            branch["id"],
            price_amount="7.00",
            effective_from="2026-02-01T00:00:00Z",
        )
        assert closed["effectiveTo"] == "2026-02-01T00:00:00Z"
        assert open_ended["effectiveTo"] is None

    def test_effective_from_not_before_effective_to_is_422(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-03-01T00:00:00Z",
                "effectiveTo": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 422

    def test_an_unknown_menu_item_id_is_404(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{'0' * 26}/branch-price",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MENU_ITEM_NOT_FOUND"

    def test_an_unknown_branch_id_is_404(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": "0" * 26,
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    async def test_a_menu_item_belonging_to_another_tenant_is_404_not_a_leak(
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
            f"/api/v1/menu-items/{other_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MENU_ITEM_NOT_FOUND"

    async def test_a_branch_belonging_to_another_tenant_is_404_not_a_leak(
        self, client: TestClient, owner: dict, menu_item: dict, session_factory
    ) -> None:
        other_tenant_id = generate_ulid()
        other_email = "otherbranch@example.com"
        other_user_id = await _seed_user(
            session_factory, tenant_id=other_tenant_id, email=other_email
        )
        await _grant_role(
            session_factory,
            tenant_id=other_tenant_id,
            user_id=other_user_id,
            permission_codes=frozenset({"branch.manage", "restaurant.manage"}),
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

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": other_branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_requires_authentication(
        self, client: TestClient, branch: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            json={
                "branchId": branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 401

    def test_denied_without_menu_manage(
        self, client: TestClient, reader_only: dict, branch: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(reader_only["token"]),
            json={
                "branchId": branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 403

    def test_denied_with_no_permission_at_all(
        self, client: TestClient, no_permission: dict, branch: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(no_permission["token"]),
            json={
                "branchId": branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 403

    async def test_a_branch_scoped_manage_holder_can_set_a_price_at_their_own_branch(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict, session_factory
    ) -> None:
        email = "branchmgr@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"menu.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(token),
            json={
                "branchId": branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 201, response.text

    async def test_a_branch_scoped_manage_holder_cannot_set_a_price_at_a_different_branch(
        self,
        client: TestClient,
        owner: dict,
        restaurant_id: str,
        branch: dict,
        menu_item: dict,
        session_factory,
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
            permission_codes=frozenset({"menu.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(token),
            json={
                "branchId": other_branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 403


class TestCreateMenuItemBranchPriceIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        body = {
            "branchId": branch["id"],
            "priceAmount": "8.50",
            "effectiveFrom": "2026-01-01T00:00:00Z",
        }
        url = f"/api/v1/menu-items/{menu_item['id']}/branch-price"

        first = client.put(url, headers=headers, json=body)
        second = client.put(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()

        history = client.get(url, headers=_auth_headers(owner["token"])).json()["data"]
        assert len(history) == 1

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/menu-items/{menu_item['id']}/branch-price"

        first = client.put(
            url,
            headers=headers,
            json={
                "branchId": branch["id"],
                "priceAmount": "8.50",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert first.status_code == 201, first.text

        second = client.put(
            url,
            headers=headers,
            json={
                "branchId": branch["id"],
                "priceAmount": "9.00",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestMenuItemBranchPriceEffectiveWindowOverlap:
    """Migration 0005's own docstring (Step 4 Decision Lock) commits to
    a clean ``EFFECTIVE_WINDOW_OVERLAP`` domain error in front of the
    table's GiST ``EXCLUDE`` constraint -- these confirm the API
    surfaces that clean 409 rather than an unhandled 500."""

    def test_an_overlapping_window_at_the_same_branch_is_409(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        _set_branch_price(
            client,
            owner,
            menu_item["id"],
            branch["id"],
            effective_from="2026-01-01T00:00:00Z",
        )

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": branch["id"],
                "priceAmount": "7.00",
                "effectiveFrom": "2026-02-01T00:00:00Z",
            },
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "EFFECTIVE_WINDOW_OVERLAP"

    def test_a_non_overlapping_window_at_the_same_branch_is_201(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        _set_branch_price(
            client,
            owner,
            menu_item["id"],
            branch["id"],
            effective_from="2026-01-01T00:00:00Z",
            effective_to="2026-02-01T00:00:00Z",
        )

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": branch["id"],
                "priceAmount": "7.00",
                "effectiveFrom": "2026-02-01T00:00:00Z",
            },
        )
        assert response.status_code == 201, response.text

    def test_an_overlapping_window_at_a_different_branch_is_201(
        self,
        client: TestClient,
        owner: dict,
        restaurant_id: str,
        branch: dict,
        menu_item: dict,
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        _set_branch_price(
            client, owner, menu_item["id"], branch["id"], effective_from="2026-01-01T00:00:00Z"
        )

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": other_branch["id"],
                "priceAmount": "7.00",
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 201, response.text


class TestListMenuItemBranchPrices:
    def test_a_read_holder_can_list_history(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        row = _set_branch_price(client, owner, menu_item["id"], branch["id"])
        response = client.get(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200, response.text
        assert [r["id"] for r in response.json()["data"]] == [row["id"]]

    def test_multiple_override_windows_all_appear(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        first = _set_branch_price(
            client,
            owner,
            menu_item["id"],
            branch["id"],
            effective_from="2026-01-01T00:00:00Z",
            effective_to="2026-02-01T00:00:00Z",
        )
        second = _set_branch_price(
            client, owner, menu_item["id"], branch["id"], effective_from="2026-02-01T00:00:00Z"
        )
        response = client.get(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
        )
        ids = {r["id"] for r in response.json()["data"]}
        assert ids == {first["id"], second["id"]}

    def test_empty_history_for_an_item_with_no_overrides(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        response = client.get(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_an_unknown_menu_item_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(
            f"/api/v1/menu-items/{'0' * 26}/branch-price", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MENU_ITEM_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, menu_item: dict) -> None:
        response = client.get(f"/api/v1/menu-items/{menu_item['id']}/branch-price")
        assert response.status_code == 401

    def test_denied_with_no_permission_at_all(
        self, client: TestClient, no_permission: dict, menu_item: dict
    ) -> None:
        response = client.get(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price",
            headers=_auth_headers(no_permission["token"]),
        )
        assert response.status_code == 403

    async def test_a_branch_scoped_reader_sees_only_their_own_branchs_rows(
        self,
        client: TestClient,
        owner: dict,
        restaurant_id: str,
        branch: dict,
        menu_item: dict,
        session_factory,
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        own_row = _set_branch_price(client, owner, menu_item["id"], branch["id"])
        _set_branch_price(client, owner, menu_item["id"], other_branch["id"])

        email = "branchreader@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"menu.read"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.get(
            f"/api/v1/menu-items/{menu_item['id']}/branch-price", headers=_auth_headers(token)
        )
        assert response.status_code == 200, response.text
        assert [r["id"] for r in response.json()["data"]] == [own_row["id"]]


class TestMenuItemBranchPriceConstraintsRemainIntact:
    async def test_effective_from_before_effective_to_check_constraint_is_still_enforced(
        self, session_factory, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        with pytest.raises(DBAPIError):
            async with UnitOfWork(session_factory, TenantContext(owner["tenant_id"])) as uow:
                await uow.session.execute(
                    text(
                        "INSERT INTO menu_item_branch_prices (id, tenant_id, branch_id, "
                        "menu_item_id, price_amount, effective_from, effective_to) VALUES "
                        "(:id, :tenant_id, :branch_id, :menu_item_id, :price, :ef, :et)"
                    ),
                    {
                        "id": generate_ulid(),
                        "tenant_id": owner["tenant_id"],
                        "branch_id": branch["id"],
                        "menu_item_id": menu_item["id"],
                        "price": "5.00",
                        "ef": "2026-03-01T00:00:00Z",
                        "et": "2026-01-01T00:00:00Z",
                    },
                )


class TestCreateMenuItemAvailability:
    def test_a_manage_holder_can_set_availability(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        data = _set_availability(client, owner, menu_item["id"], branch["id"], is_available=False)
        assert data["menuItemId"] == menu_item["id"]
        assert data["branchId"] == branch["id"]
        assert data["isAvailable"] is False

    def test_an_unknown_menu_item_id_is_404(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{'0' * 26}/availability",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": branch["id"],
                "isAvailable": False,
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MENU_ITEM_NOT_FOUND"

    def test_an_unknown_branch_id_is_404(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/availability",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": "0" * 26,
                "isAvailable": False,
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_requires_authentication(
        self, client: TestClient, branch: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/availability",
            json={
                "branchId": branch["id"],
                "isAvailable": False,
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 401

    def test_denied_without_menu_manage(
        self, client: TestClient, reader_only: dict, branch: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/availability",
            headers=_auth_headers(reader_only["token"]),
            json={
                "branchId": branch["id"],
                "isAvailable": False,
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 403

    async def test_a_branch_scoped_manage_holder_cannot_set_availability_at_a_different_branch(
        self,
        client: TestClient,
        owner: dict,
        restaurant_id: str,
        branch: dict,
        menu_item: dict,
        session_factory,
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]

        email = "scoped2@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"menu.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/availability",
            headers=_auth_headers(token),
            json={
                "branchId": other_branch["id"],
                "isAvailable": False,
                "effectiveFrom": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 403


class TestCreateMenuItemAvailabilityIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        body = {
            "branchId": branch["id"],
            "isAvailable": False,
            "effectiveFrom": "2026-01-01T00:00:00Z",
        }
        url = f"/api/v1/menu-items/{menu_item['id']}/availability"

        first = client.put(url, headers=headers, json=body)
        second = client.put(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()

        history = client.get(url, headers=_auth_headers(owner["token"])).json()["data"]
        assert len(history) == 1


class TestMenuItemAvailabilityEffectiveWindowOverlap:
    def test_an_overlapping_window_at_the_same_branch_is_409(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        _set_availability(
            client, owner, menu_item["id"], branch["id"], effective_from="2026-01-01T00:00:00Z"
        )

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/availability",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": branch["id"],
                "isAvailable": True,
                "effectiveFrom": "2026-02-01T00:00:00Z",
            },
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "EFFECTIVE_WINDOW_OVERLAP"

    def test_a_non_overlapping_window_at_the_same_branch_is_201(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        _set_availability(
            client,
            owner,
            menu_item["id"],
            branch["id"],
            effective_from="2026-01-01T00:00:00Z",
            effective_to="2026-02-01T00:00:00Z",
        )

        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/availability",
            headers=_auth_headers(owner["token"]),
            json={
                "branchId": branch["id"],
                "isAvailable": True,
                "effectiveFrom": "2026-02-01T00:00:00Z",
            },
        )
        assert response.status_code == 201, response.text


class TestListMenuItemAvailabilities:
    def test_a_read_holder_can_list_history(
        self, client: TestClient, owner: dict, branch: dict, menu_item: dict
    ) -> None:
        row = _set_availability(client, owner, menu_item["id"], branch["id"])
        response = client.get(
            f"/api/v1/menu-items/{menu_item['id']}/availability",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200, response.text
        assert [r["id"] for r in response.json()["data"]] == [row["id"]]

    def test_empty_history_for_an_item_with_no_overrides(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        response = client.get(
            f"/api/v1/menu-items/{menu_item['id']}/availability",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_an_unknown_menu_item_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(
            f"/api/v1/menu-items/{'0' * 26}/availability", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MENU_ITEM_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, menu_item: dict) -> None:
        response = client.get(f"/api/v1/menu-items/{menu_item['id']}/availability")
        assert response.status_code == 401

    async def test_a_branch_scoped_reader_sees_only_their_own_branchs_rows(
        self,
        client: TestClient,
        owner: dict,
        restaurant_id: str,
        branch: dict,
        menu_item: dict,
        session_factory,
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        own_row = _set_availability(client, owner, menu_item["id"], branch["id"])
        _set_availability(client, owner, menu_item["id"], other_branch["id"])

        email = "availreader@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"menu.read"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.get(
            f"/api/v1/menu-items/{menu_item['id']}/availability", headers=_auth_headers(token)
        )
        assert response.status_code == 200, response.text
        assert [r["id"] for r in response.json()["data"]] == [own_row["id"]]


class TestMenuItemModifierGroupsRouteStaysIsolated:
    """Confirms the pre-existing modifier-groups route on the same
    router file is unaffected by these additions."""

    def test_modifier_groups_route_still_exists_and_is_unaffected(
        self, client: TestClient, owner: dict, menu_item: dict
    ) -> None:
        response = client.put(
            f"/api/v1/menu-items/{menu_item['id']}/modifier-groups",
            headers=_auth_headers(owner["token"]),
            json={"modifierGroupIds": []},
        )
        assert response.status_code == 200, response.text
