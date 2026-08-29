"""End-to-end HTTP integration tests for Inventory + Recipe (Sprint 7
Step 5) against real PostgreSQL.

The single highest-value scenario here -- and the reason this suite
exists at all, not just the unit layer -- is proving the real
``stock_movements`` trigger actually maintains ``InventoryItem
.quantity_on_hand``: ``tests/unit/modules/operations/fakes.py`` fakes
that balance-maintenance in Python, which proves the use case *reads
the balance back*, not that Postgres actually updates it. Only a real
Postgres integration test can prove the trigger itself works.
"""

from __future__ import annotations

from collections.abc import Iterator
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

_PERMISSIONS = frozenset(
    {
        "inventory.manage",
        "inventory.read",
        "menu.manage",
        "menu.read",
        "inventory_food.manage",
        "inventory_food.read",
    }
)


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
                default_scope=RoleScope.BRANCH if branch_id is not None else RoleScope.TENANT,
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


async def _seed_menu(session_factory, *, tenant_id: str) -> dict[str, str]:
    restaurant_id = generate_ulid()
    branch_id = generate_ulid()
    category_id = generate_ulid()
    item_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO restaurants (id, tenant_id, legal_name, display_name, "
                "default_currency_code) VALUES (:id, :tenant_id, 'R', 'R', 'USD')"
            ),
            {"id": restaurant_id, "tenant_id": tenant_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO branches (id, tenant_id, restaurant_id, name, "
                "allow_negative_stock, invoice_prefix) "
                "VALUES (:id, :tenant_id, :restaurant_id, 'Downtown', false, 'TST')"
            ),
            {"id": branch_id, "tenant_id": tenant_id, "restaurant_id": restaurant_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO menu_categories (id, tenant_id, restaurant_id, name) "
                "VALUES (:id, :tenant_id, :restaurant_id, 'Mains')"
            ),
            {"id": category_id, "tenant_id": tenant_id, "restaurant_id": restaurant_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO menu_items (id, tenant_id, menu_category_id, name, price_amount, "
                "currency_code) VALUES (:id, :tenant_id, :category_id, 'Burger', 10.00, 'USD')"
            ),
            {"id": item_id, "tenant_id": tenant_id, "category_id": category_id},
        )
    return {
        "restaurant_id": restaurant_id,
        "branch_id": branch_id,
        "category_id": category_id,
        "menu_item_id": item_id,
    }


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def owner(session_factory, client: TestClient):
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory, tenant_id=tenant_id, user_id=user_id, permission_codes=_PERMISSIONS
    )
    token = _login_sync(client, tenant_id=tenant_id, email=email)
    menu = await _seed_menu(session_factory, tenant_id=tenant_id)
    return {"tenant_id": tenant_id, "user_id": user_id, "token": token, **menu}


class TestInventoryLifecycle:
    def test_stock_movements_are_maintained_by_the_real_database_trigger(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]

        category_resp = client.post(
            "/api/v1/inventory-categories",
            headers=headers,
            json={"name": "Produce", "categoryType": "beverage"},
        )
        assert category_resp.status_code == 201, category_resp.text
        category_id = category_resp.json()["data"]["id"]

        item_resp = client.post(
            f"/api/v1/branches/{branch_id}/inventory-items",
            headers=headers,
            json={
                "inventoryCategoryId": category_id,
                "name": "Beef Patty",
                "unit": "each",
                "reorderPoint": "10",
            },
        )
        assert item_resp.status_code == 201, item_resp.text
        item = item_resp.json()["data"]
        assert Decimal(item["quantityOnHand"]) == Decimal(0)
        item_id = item["id"]

        receipt_movement = client.post(
            f"/api/v1/inventory-items/{item_id}/stock-movements",
            headers=headers,
            json={
                "movementType": "adjustment",
                "quantityDelta": "50",
                "reason": "initial stock",
                "approvedByUserId": owner["user_id"],
            },
        )
        assert receipt_movement.status_code == 201, receipt_movement.text
        assert Decimal(receipt_movement.json()["data"]["quantityDelta"]) == Decimal(50)

        after_receipt = client.get(
            f"/api/v1/branches/{branch_id}/inventory-items/{item_id}", headers=headers
        )
        assert Decimal(after_receipt.json()["data"]["quantityOnHand"]) == Decimal(50)

        waste_movement = client.post(
            f"/api/v1/inventory-items/{item_id}/stock-movements",
            headers=headers,
            json={"movementType": "waste", "quantityDelta": "10"},
        )
        assert waste_movement.status_code == 201, waste_movement.text
        # The use case server-forces waste deltas negative regardless of
        # the caller-supplied sign -- verified here against the real
        # persisted row, not an in-memory fake.
        assert Decimal(waste_movement.json()["data"]["quantityDelta"]) == Decimal(-10)

        after_waste = client.get(
            f"/api/v1/branches/{branch_id}/inventory-items/{item_id}", headers=headers
        )
        assert Decimal(after_waste.json()["data"]["quantityOnHand"]) == Decimal(40)

        movements_resp = client.get(
            f"/api/v1/inventory-items/{item_id}/stock-movements", headers=headers
        )
        assert movements_resp.status_code == 200
        assert len(movements_resp.json()["data"]) == 2

        over_waste = client.post(
            f"/api/v1/inventory-items/{item_id}/stock-movements",
            headers=headers,
            json={"movementType": "waste", "quantityDelta": "1000"},
        )
        assert over_waste.status_code == 409, over_waste.text
        assert over_waste.json()["error"]["code"] == "INSUFFICIENT_STOCK"

        missing_reason = client.post(
            f"/api/v1/inventory-items/{item_id}/stock-movements",
            headers=headers,
            json={"movementType": "adjustment", "quantityDelta": "5"},
        )
        assert missing_reason.status_code == 422, missing_reason.text
        assert missing_reason.json()["error"]["code"] == "STOCK_ADJUSTMENT_REQUIRES_REASON"

    def test_revises_a_recipe_referencing_a_real_inventory_item(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        category_resp = client.post(
            "/api/v1/inventory-categories",
            headers=headers,
            json={"name": "Produce", "categoryType": "beverage"},
        )
        category_id = category_resp.json()["data"]["id"]
        item_resp = client.post(
            f"/api/v1/branches/{owner['branch_id']}/inventory-items",
            headers=headers,
            json={"inventoryCategoryId": category_id, "name": "Bun", "unit": "each"},
        )
        inventory_item_id = item_resp.json()["data"]["id"]

        revise_resp = client.put(
            f"/api/v1/menu-items/{owner['menu_item_id']}/recipe",
            headers=headers,
            json={
                "name": "Burger recipe",
                "ingredients": [
                    {"inventoryItemId": inventory_item_id, "quantity": "1", "unit": "each"}
                ],
            },
        )
        assert revise_resp.status_code == 201, revise_resp.text
        recipe = revise_resp.json()["data"]
        assert recipe["version"] == 1
        assert len(recipe["ingredients"]) == 1

        get_resp = client.get(f"/api/v1/menu-items/{owner['menu_item_id']}/recipe", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == recipe["id"]

        revise_again = client.put(
            f"/api/v1/menu-items/{owner['menu_item_id']}/recipe",
            headers=headers,
            json={"name": "Burger recipe v2", "ingredients": []},
        )
        assert revise_again.status_code == 201, revise_again.text
        assert revise_again.json()["data"]["version"] == 2

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/inventory-categories", json={"name": "Produce", "categoryType": "beverage"}
        )
        assert response.status_code == 401

    async def test_denied_without_inventory_manage(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        email = "noperm@example.com"
        await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            "/api/v1/inventory-categories",
            headers=_auth_headers(token),
            json={"name": "Produce", "categoryType": "beverage"},
        )
        assert response.status_code == 403

    async def test_branch_scoped_inventory_manage_can_create_a_category(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        email = "branch-inventory-manager@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"inventory.manage"}),
            branch_id=owner["branch_id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            "/api/v1/inventory-categories",
            headers=_auth_headers(token),
            json={"name": "Produce", "categoryType": "beverage"},
        )
        assert response.status_code == 201, response.text


class TestFoodVsBeverageGate:
    """2026-08-14 product decision: food-inventory tracking is de-scoped
    from the default Inventory Manager workflow (recipe-based deduction
    can't be trusted to reflect real chef usage) -- liquor/beverage
    inventory stays fully tracked. A branch-scoped inventory.manage-only
    grant (the real seeded Inventory Manager shape) can freely manage
    beverage categories/items, but a food category or item additionally
    needs the dedicated inventory_food.manage/inventory_food.read (at
    any scope) -- NOT menu.manage/menu.read, since the real Inventory
    Manager role already holds those two for recipe editing; reusing
    them would have restricted nothing. RBAC here is permission-based
    throughout, never role-name-based -- Restaurant Manager/Tenant Owner
    hold the new codes by default, Inventory Manager does not."""

    async def _inventory_only_token(self, client: TestClient, owner: dict, session_factory) -> str:
        email = "inventory-only@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"inventory.manage", "inventory.read"}),
            branch_id=owner["branch_id"],
        )
        return _login_sync(client, tenant_id=owner["tenant_id"], email=email)

    async def test_an_inventory_only_grant_is_denied_creating_a_food_category(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        token = await self._inventory_only_token(client, owner, session_factory)

        response = client.post(
            "/api/v1/inventory-categories",
            headers=_auth_headers(token),
            json={"name": "Produce", "categoryType": "food"},
        )
        assert response.status_code == 403, response.text

    async def test_an_inventory_only_grant_can_still_create_a_beverage_category(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        token = await self._inventory_only_token(client, owner, session_factory)

        response = client.post(
            "/api/v1/inventory-categories",
            headers=_auth_headers(token),
            json={"name": "Liquor", "categoryType": "beverage"},
        )
        assert response.status_code == 201, response.text

    async def test_an_inventory_only_grant_does_not_see_food_categories_in_the_list(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        headers = _auth_headers(owner["token"])
        client.post(
            "/api/v1/inventory-categories",
            headers=headers,
            json={"name": "Liquor", "categoryType": "beverage"},
        )
        client.post(
            "/api/v1/inventory-categories",
            headers=headers,
            json={"name": "Produce", "categoryType": "food"},
        )
        token = await self._inventory_only_token(client, owner, session_factory)

        response = client.get("/api/v1/inventory-categories", headers=_auth_headers(token))
        assert response.status_code == 200, response.text
        names = {c["name"] for c in response.json()["data"]}
        assert names == {"Liquor"}

    async def test_owner_with_inventory_food_manage_sees_both_and_can_create_food(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        client.post(
            "/api/v1/inventory-categories",
            headers=headers,
            json={"name": "Liquor", "categoryType": "beverage"},
        )
        food_resp = client.post(
            "/api/v1/inventory-categories",
            headers=headers,
            json={"name": "Produce", "categoryType": "food"},
        )
        assert food_resp.status_code == 201, food_resp.text

        response = client.get("/api/v1/inventory-categories", headers=headers)
        names = {c["name"] for c in response.json()["data"]}
        assert names == {"Liquor", "Produce"}

    async def test_an_inventory_only_grant_cannot_create_an_item_under_a_food_category(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        headers = _auth_headers(owner["token"])
        category_resp = client.post(
            "/api/v1/inventory-categories",
            headers=headers,
            json={"name": "Produce", "categoryType": "food"},
        )
        category_id = category_resp.json()["data"]["id"]
        token = await self._inventory_only_token(client, owner, session_factory)

        response = client.post(
            f"/api/v1/branches/{owner['branch_id']}/inventory-items",
            headers=_auth_headers(token),
            json={"inventoryCategoryId": category_id, "name": "Chicken", "unit": "kg"},
        )
        assert response.status_code == 403, response.text
