"""End-to-end HTTP integration tests for the Order -> Kitchen -> Bill ->
Payment lifecycle (Sprint 7 Steps 3-4) against real PostgreSQL.

Scoped deliberately leaner than the restaurant module's own per-router
integration density (Sprint 7 Step 8's own disclosed scoping): one
consolidated file walks the full real-HTTP lifecycle end to end
(exercising RLS, real Postgres transactions, and camelCase
serialization all at once) rather than one file per router with
exhaustive per-endpoint permutations -- that density already exists at
the unit layer (tests/unit/modules/operations) against in-memory
fakes. This file's job is to prove the wiring between routers, real
repositories, and Postgres itself, plus the RBAC/tenant-isolation
boundaries unit tests cannot exercise (no real auth/HTTP layer).
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
        "order.manage",
        "order.read",
        "kitchen.manage",
        "kitchen.read",
        "billing.manage",
        "billing.read",
        "billing.refund",
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


async def _seed_menu(session_factory, *, tenant_id: str) -> dict[str, str]:
    """Seeds Restaurant -> Branch -> MenuCategory -> MenuItem via raw SQL,
    the same convention every other integration test file in this
    codebase uses for fixture data outside the router under test."""
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
                "INSERT INTO branches (id, tenant_id, restaurant_id, name) "
                "VALUES (:id, :tenant_id, :restaurant_id, 'Downtown')"
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
    """A tenant-wide grant across every permission this lifecycle needs."""
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory, tenant_id=tenant_id, user_id=user_id, permission_codes=_PERMISSIONS
    )
    token = _login_sync(client, tenant_id=tenant_id, email=email)
    menu = await _seed_menu(session_factory, tenant_id=tenant_id)
    return {"tenant_id": tenant_id, "user_id": user_id, "token": token, **menu}


class TestOrderKitchenBillingPaymentLifecycle:
    def test_full_lifecycle_from_open_order_to_settled_payment(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]

        create_resp = client.post(
            f"/api/v1/branches/{branch_id}/orders",
            headers=headers,
            json={"orderSource": "pos"},
        )
        assert create_resp.status_code == 201, create_resp.text
        order = create_resp.json()["data"]
        assert order["status"] == "open"
        order_id = order["id"]

        item_resp = client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 2},
        )
        assert item_resp.status_code == 201, item_resp.text
        order_with_item = item_resp.json()["data"]
        assert Decimal(order_with_item["subtotalAmount"]) == Decimal("20.00")

        fire_resp = client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        assert fire_resp.status_code == 200, fire_resp.text
        assert fire_resp.json()["data"]["status"] == "fired"

        tickets_resp = client.get(f"/api/v1/branches/{branch_id}/kitchen-tickets", headers=headers)
        assert tickets_resp.status_code == 200, tickets_resp.text
        tickets = tickets_resp.json()["data"]
        assert len(tickets) == 1
        ticket_id = tickets[0]["id"]
        assert tickets[0]["status"] == "fired"

        start_resp = client.post(
            f"/api/v1/kitchen-tickets/{ticket_id}/status",
            headers=headers,
            json={"status": "in_progress"},
        )
        assert start_resp.status_code == 200, start_resp.text

        ready_resp = client.post(
            f"/api/v1/kitchen-tickets/{ticket_id}/status",
            headers=headers,
            json={"status": "ready"},
        )
        assert ready_resp.status_code == 200, ready_resp.text
        assert ready_resp.json()["data"]["status"] == "ready"

        tax_resp = client.post(
            "/api/v1/taxes", headers=headers, json={"name": "VAT", "rate": "0.10"}
        )
        assert tax_resp.status_code == 201, tax_resp.text

        bill_resp = client.post(f"/api/v1/orders/{order_id}/bill", headers=headers)
        assert bill_resp.status_code == 201, bill_resp.text
        bill = bill_resp.json()["data"]
        assert bill["status"] == "open"
        assert Decimal(bill["subtotalAmount"]) == Decimal("20.00")
        assert Decimal(bill["taxAmount"]) == Decimal("2.00")
        bill_id = bill["id"]

        adjustment_resp = client.post(
            f"/api/v1/bills/{bill_id}/adjustments",
            headers=headers,
            json={"adjustmentType": "discount", "amount": "2.00", "reason": "loyalty"},
        )
        assert adjustment_resp.status_code == 201, adjustment_resp.text
        adjusted_bill = adjustment_resp.json()["data"]
        assert Decimal(adjusted_bill["adjustmentsTotal"]) == Decimal("-2.00")
        amount_due = Decimal(adjusted_bill["amountDue"])
        assert amount_due == Decimal("20.00")  # 20 subtotal + 2 tax - 2 discount

        tip_amount = Decimal("3.00")
        payment_resp = client.post(
            f"/api/v1/bills/{bill_id}/payments",
            headers=headers,
            json={
                "tenderType": "cash",
                # RecordPaymentUseCase applies (amount - tipAmount) to amount_due,
                # so the bill's own share must be topped up by the tip to fully pay.
                "amount": str(amount_due + tip_amount),
                "tipAmount": str(tip_amount),
            },
        )
        assert payment_resp.status_code == 201, payment_resp.text
        payment = payment_resp.json()["data"]
        assert payment["status"] == "settled"
        payment_id = payment["id"]

        order_after_payment = client.get(
            f"/api/v1/branches/{branch_id}/orders/{order_id}", headers=headers
        )
        assert order_after_payment.status_code == 200
        assert order_after_payment.json()["data"]["status"] == "closed"

        list_payments_resp = client.get(f"/api/v1/bills/{bill_id}/payments", headers=headers)
        assert list_payments_resp.status_code == 200
        assert len(list_payments_resp.json()["data"]) == 1

        refund_resp = client.post(
            f"/api/v1/payments/{payment_id}/refund",
            headers=headers,
            json={"approvedByUserId": owner["user_id"], "amount": "5.00"},
        )
        assert refund_resp.status_code == 201, refund_resp.text
        assert refund_resp.json()["data"]["status"] == "processed"

    def test_requires_authentication(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            f"/api/v1/branches/{owner['branch_id']}/orders", json={"orderSource": "pos"}
        )
        assert response.status_code == 401

    async def test_denied_without_order_manage(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        email = "noperm@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
        _ = user_id

        response = client.post(
            f"/api/v1/branches/{owner['branch_id']}/orders",
            headers=_auth_headers(token),
            json={"orderSource": "pos"},
        )
        assert response.status_code == 403

    async def test_an_order_in_another_tenant_is_a_404_not_a_403(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        """Cross-tenant order lookup resolves as not-found through the
        tenant-scoped repository, never leaking existence via a 403."""
        create_resp = client.post(
            f"/api/v1/branches/{owner['branch_id']}/orders",
            headers=_auth_headers(owner["token"]),
            json={"orderSource": "pos"},
        )
        order_id = create_resp.json()["data"]["id"]

        other_tenant_id = generate_ulid()
        other_email = "other-owner@example.com"
        other_user_id = await _seed_user(
            session_factory, tenant_id=other_tenant_id, email=other_email
        )
        await _grant_role(
            session_factory,
            tenant_id=other_tenant_id,
            user_id=other_user_id,
            permission_codes=_PERMISSIONS,
        )
        other_token = _login_sync(client, tenant_id=other_tenant_id, email=other_email)
        other_menu = await _seed_menu(session_factory, tenant_id=other_tenant_id)

        response = client.get(
            f"/api/v1/branches/{other_menu['branch_id']}/orders/{order_id}",
            headers=_auth_headers(other_token),
        )
        assert response.status_code == 404
