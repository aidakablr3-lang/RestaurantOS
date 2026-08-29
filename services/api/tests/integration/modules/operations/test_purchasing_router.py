"""End-to-end HTTP integration tests for Supplier + PurchaseOrder +
GoodsReceipt (Sprint 7 Step 6) against real PostgreSQL.

Like the inventory suite, the highest-value scenario here is
``ConfirmGoodsReceiptUseCase`` writing a real ``StockMovement(movement_
type='receipt')`` row and the real ``stock_movements`` trigger actually
crediting the linked ``InventoryItem.quantity_on_hand`` -- something a
fakes-backed unit test can only assert was *asked for*, not that
Postgres itself carried it out.
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
    {"purchasing.manage", "purchasing.read", "inventory.manage", "inventory.read"}
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


async def _seed_branch(session_factory, *, tenant_id: str) -> str:
    restaurant_id = generate_ulid()
    branch_id = generate_ulid()
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
                "INSERT INTO branches (id, tenant_id, restaurant_id, name, invoice_prefix) "
                "VALUES (:id, :tenant_id, :restaurant_id, 'Downtown', 'TST')"
            ),
            {"id": branch_id, "tenant_id": tenant_id, "restaurant_id": restaurant_id},
        )
    return branch_id


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
    branch_id = await _seed_branch(session_factory, tenant_id=tenant_id)
    return {"tenant_id": tenant_id, "user_id": user_id, "token": token, "branch_id": branch_id}


def _create_inventory_item(client: TestClient, owner: dict) -> str:
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
        json={"inventoryCategoryId": category_id, "name": "Tomatoes", "unit": "kg"},
    )
    assert item_resp.status_code == 201, item_resp.text
    return item_resp.json()["data"]["id"]


def _create_supplier(client: TestClient, owner: dict) -> str:
    response = client.post(
        "/api/v1/suppliers", headers=_auth_headers(owner["token"]), json={"name": "Fresh Foods Co"}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


class TestPurchasingLifecycle:
    def test_full_lifecycle_receipt_credits_real_inventory_via_the_db_trigger(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]
        supplier_id = _create_supplier(client, owner)
        inventory_item_id = _create_inventory_item(client, owner)

        po_resp = client.post(
            f"/api/v1/branches/{branch_id}/purchase-orders",
            headers=headers,
            json={"supplierId": supplier_id},
        )
        assert po_resp.status_code == 201, po_resp.text
        po = po_resp.json()["data"]
        assert po["status"] == "draft"
        po_id = po["id"]

        add_item_resp = client.post(
            f"/api/v1/purchase-orders/{po_id}/items",
            headers=headers,
            json={"inventoryItemId": inventory_item_id, "quantityOrdered": "20"},
        )
        assert add_item_resp.status_code == 201, add_item_resp.text
        po_item_id = add_item_resp.json()["data"]["items"][0]["id"]

        send_resp = client.post(f"/api/v1/purchase-orders/{po_id}/send", headers=headers)
        assert send_resp.status_code == 200, send_resp.text
        assert send_resp.json()["data"]["status"] == "sent"

        receipt_resp = client.post(
            f"/api/v1/purchase-orders/{po_id}/receipts",
            headers=headers,
            json={"lines": [{"purchaseOrderItemId": po_item_id, "quantityReceived": "12"}]},
        )
        assert receipt_resp.status_code == 201, receipt_resp.text
        receipt = receipt_resp.json()["data"]
        assert receipt["status"] == "confirmed"
        assert receipt["hasDiscrepancy"] is False
        assert receipt["purchaseOrder"]["status"] == "partially_received"

        item_after_receipt = client.get(
            f"/api/v1/branches/{branch_id}/inventory-items/{inventory_item_id}", headers=headers
        )
        assert Decimal(item_after_receipt.json()["data"]["quantityOnHand"]) == Decimal(12)

        over_receipt_resp = client.post(
            f"/api/v1/purchase-orders/{po_id}/receipts",
            headers=headers,
            json={"lines": [{"purchaseOrderItemId": po_item_id, "quantityReceived": "20"}]},
        )
        assert over_receipt_resp.status_code == 201, over_receipt_resp.text
        over_receipt = over_receipt_resp.json()["data"]
        # 12 + 20 = 32 received against 20 ordered -- flagged, not rejected.
        assert over_receipt["hasDiscrepancy"] is True
        assert over_receipt["purchaseOrder"]["status"] == "fully_received"

        item_after_second_receipt = client.get(
            f"/api/v1/branches/{branch_id}/inventory-items/{inventory_item_id}", headers=headers
        )
        assert Decimal(item_after_second_receipt.json()["data"]["quantityOnHand"]) == Decimal(32)

    def test_cancelling_a_draft_purchase_order(self, client: TestClient, owner: dict) -> None:
        headers = _auth_headers(owner["token"])
        supplier_id = _create_supplier(client, owner)
        po_resp = client.post(
            f"/api/v1/branches/{owner['branch_id']}/purchase-orders",
            headers=headers,
            json={"supplierId": supplier_id},
        )
        po_id = po_resp.json()["data"]["id"]

        cancel_resp = client.post(f"/api/v1/purchase-orders/{po_id}/cancel", headers=headers)
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["data"]["status"] == "canceled"

    def test_sending_an_empty_purchase_order_is_rejected(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        supplier_id = _create_supplier(client, owner)
        po_resp = client.post(
            f"/api/v1/branches/{owner['branch_id']}/purchase-orders",
            headers=headers,
            json={"supplierId": supplier_id},
        )
        po_id = po_resp.json()["data"]["id"]

        send_resp = client.post(f"/api/v1/purchase-orders/{po_id}/send", headers=headers)
        assert send_resp.status_code == 409, send_resp.text
        assert send_resp.json()["error"]["code"] == "PURCHASE_ORDER_HAS_NO_ITEMS"

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.post("/api/v1/suppliers", json={"name": "Fresh Foods Co"})
        assert response.status_code == 401

    async def test_denied_without_purchasing_manage(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        email = "noperm@example.com"
        await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            "/api/v1/suppliers", headers=_auth_headers(token), json={"name": "Fresh Foods Co"}
        )
        assert response.status_code == 403
