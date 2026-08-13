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
        "menu.manage",
        "inventory.manage",
        "inventory.read",
        "table.read",
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
    codebase uses for fixture data outside the router under test.
    Seeds a second, ``bar``-station item alongside the default
    ``kitchen``-station one so station-routing tests have both to work
    with, plus one dine-in ``Table`` for the table-status-cascade tests."""
    restaurant_id = generate_ulid()
    branch_id = generate_ulid()
    category_id = generate_ulid()
    item_id = generate_ulid()
    bar_item_id = generate_ulid()
    table_zone_id = generate_ulid()
    table_id = generate_ulid()
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
        await uow.session.execute(
            text(
                "INSERT INTO menu_items (id, tenant_id, menu_category_id, name, price_amount, "
                "currency_code, station) VALUES (:id, :tenant_id, :category_id, 'Soda', 3.00, "
                "'USD', 'bar')"
            ),
            {"id": bar_item_id, "tenant_id": tenant_id, "category_id": category_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO table_zones (id, tenant_id, branch_id, name) "
                "VALUES (:id, :tenant_id, :branch_id, 'Main Floor')"
            ),
            {"id": table_zone_id, "tenant_id": tenant_id, "branch_id": branch_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO tables (id, tenant_id, branch_id, table_zone_id, table_number, "
                "capacity) VALUES (:id, :tenant_id, :branch_id, :table_zone_id, '12', 4)"
            ),
            {
                "id": table_id,
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "table_zone_id": table_zone_id,
            },
        )
    return {
        "restaurant_id": restaurant_id,
        "branch_id": branch_id,
        "category_id": category_id,
        "menu_item_id": item_id,
        "bar_menu_item_id": bar_item_id,
        "table_id": table_id,
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

        table_id = owner["table_id"]
        create_resp = client.post(
            f"/api/v1/branches/{branch_id}/orders",
            headers=headers,
            json={"orderSource": "pos", "tableId": table_id},
        )
        assert create_resp.status_code == 201, create_resp.text
        order = create_resp.json()["data"]
        assert order["status"] == "open"
        order_id = order["id"]

        table_after_create = client.get(f"/api/v1/branches/{branch_id}/tables", headers=headers)
        assert table_after_create.status_code == 200
        seated_table = next(t for t in table_after_create.json()["data"] if t["id"] == table_id)
        assert seated_table["status"] == "occupied"

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
        # The ticket-level bump cascades down to its own items -- nobody
        # bumped this item individually, so it started out "queued".
        assert all(item["status"] == "in_progress" for item in start_resp.json()["data"]["items"])

        ready_resp = client.post(
            f"/api/v1/kitchen-tickets/{ticket_id}/status",
            headers=headers,
            json={"status": "ready"},
        )
        assert ready_resp.status_code == 200, ready_resp.text
        assert ready_resp.json()["data"]["status"] == "ready"
        assert all(item["status"] == "ready" for item in ready_resp.json()["data"]["items"])

        served_resp = client.post(
            f"/api/v1/kitchen-tickets/{ticket_id}/status",
            headers=headers,
            json={"status": "served"},
        )
        assert served_resp.status_code == 200, served_resp.text
        # This ticket carries the order's only item, so serving it also
        # cascades the underlying OrderItem to "served" and, since that
        # was the order's last outstanding item, the Order itself.
        order_after_serve = client.get(
            f"/api/v1/branches/{branch_id}/orders/{order_id}", headers=headers
        )
        assert order_after_serve.status_code == 200
        served_order = order_after_serve.json()["data"]
        assert served_order["status"] == "served"
        assert all(item["lineStatus"] == "served" for item in served_order["items"])

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

        # No tip anywhere: the customer pays exactly amount_due (P0
        # correction, 2026-08-12 -- tip is not part of the restaurant bill).
        payment_resp = client.post(
            f"/api/v1/bills/{bill_id}/payments",
            headers=headers,
            json={"tenderType": "cash", "amount": str(amount_due)},
        )
        assert payment_resp.status_code == 201, payment_resp.text
        payment = payment_resp.json()["data"]
        assert payment["status"] == "settled"
        assert Decimal(payment["tipAmount"]) == Decimal(0)
        payment_id = payment["id"]

        bill_after_payment = client.get(f"/api/v1/bills/{bill_id}", headers=headers)
        assert bill_after_payment.status_code == 200
        settled_bill = bill_after_payment.json()["data"]
        assert settled_bill["status"] == "closed"
        assert Decimal(settled_bill["amountDue"]) == Decimal(0)
        assert Decimal(settled_bill["amountPaid"]) == amount_due

        order_after_payment = client.get(
            f"/api/v1/branches/{branch_id}/orders/{order_id}", headers=headers
        )
        assert order_after_payment.status_code == 200
        assert order_after_payment.json()["data"]["status"] == "closed"

        # The other half of the P0 correction: the table is released
        # automatically in the same transaction as the closing payment --
        # no separate manual step required.
        table_after_payment = client.get(f"/api/v1/branches/{branch_id}/tables", headers=headers)
        assert table_after_payment.status_code == 200
        released_table = next(t for t in table_after_payment.json()["data"] if t["id"] == table_id)
        assert released_table["status"] == "available"

        list_payments_resp = client.get(f"/api/v1/bills/{bill_id}/payments", headers=headers)
        assert list_payments_resp.status_code == 200
        assert len(list_payments_resp.json()["data"]) == 1

        # Refund is retired from the active product surface -- the route
        # no longer exists at all.
        refund_resp = client.post(
            f"/api/v1/payments/{payment_id}/refund",
            headers=headers,
            json={"approvedByUserId": owner["user_id"], "amount": "5.00"},
        )
        assert refund_resp.status_code == 404, refund_resp.text

    def test_overpayment_is_rejected(self, client: TestClient, owner: dict) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]

        create_resp = client.post(
            f"/api/v1/branches/{branch_id}/orders", headers=headers, json={"orderSource": "pos"}
        )
        order_id = create_resp.json()["data"]["id"]
        client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 1},
        )
        client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        bill_resp = client.post(f"/api/v1/orders/{order_id}/bill", headers=headers)
        bill_id = bill_resp.json()["data"]["id"]
        amount_due = Decimal(bill_resp.json()["data"]["amountDue"])

        over_resp = client.post(
            f"/api/v1/bills/{bill_id}/payments",
            headers=headers,
            json={"tenderType": "cash", "amount": str(amount_due + Decimal("1.00"))},
        )
        assert over_resp.status_code == 409, over_resp.text

        exact_resp = client.post(
            f"/api/v1/bills/{bill_id}/payments",
            headers=headers,
            json={"tenderType": "cash", "amount": str(amount_due)},
        )
        assert exact_resp.status_code == 201, exact_resp.text
        assert exact_resp.json()["data"]["status"] == "settled"

    def test_partial_then_full_payment_releases_the_table_only_once_settled(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]
        table_id = owner["table_id"]

        create_resp = client.post(
            f"/api/v1/branches/{branch_id}/orders",
            headers=headers,
            json={"orderSource": "pos", "tableId": table_id},
        )
        order_id = create_resp.json()["data"]["id"]
        client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 2},
        )
        client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        bill_resp = client.post(f"/api/v1/orders/{order_id}/bill", headers=headers)
        bill_id = bill_resp.json()["data"]["id"]
        amount_due = Decimal(bill_resp.json()["data"]["amountDue"])
        half = (amount_due / 2).quantize(Decimal("0.01"))

        partial_resp = client.post(
            f"/api/v1/bills/{bill_id}/payments",
            headers=headers,
            json={"tenderType": "cash", "amount": str(half)},
        )
        assert partial_resp.status_code == 201, partial_resp.text

        bill_after_partial = client.get(f"/api/v1/bills/{bill_id}", headers=headers).json()["data"]
        assert bill_after_partial["status"] == "partially_paid"
        assert Decimal(bill_after_partial["amountDue"]) == amount_due - half

        table_after_partial = client.get(
            f"/api/v1/branches/{branch_id}/tables", headers=headers
        ).json()["data"]
        assert next(t for t in table_after_partial if t["id"] == table_id)["status"] == "occupied"

        final_resp = client.post(
            f"/api/v1/bills/{bill_id}/payments",
            headers=headers,
            json={"tenderType": "cash", "amount": str(amount_due - half)},
        )
        assert final_resp.status_code == 201, final_resp.text

        bill_after_final = client.get(f"/api/v1/bills/{bill_id}", headers=headers).json()["data"]
        assert bill_after_final["status"] == "closed"
        assert Decimal(bill_after_final["amountDue"]) == Decimal(0)

        order_after_final = client.get(
            f"/api/v1/branches/{branch_id}/orders/{order_id}", headers=headers
        ).json()["data"]
        assert order_after_final["status"] == "closed"

        table_after_final = client.get(
            f"/api/v1/branches/{branch_id}/tables", headers=headers
        ).json()["data"]
        assert next(t for t in table_after_final if t["id"] == table_id)["status"] == "available"

    def test_voids_an_added_item_and_backs_out_its_cost(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]

        create_resp = client.post(
            f"/api/v1/branches/{branch_id}/orders", headers=headers, json={"orderSource": "pos"}
        )
        order_id = create_resp.json()["data"]["id"]

        first_item = client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 1},
        ).json()["data"]["items"][0]

        second_resp = client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 1},
        )
        second_item = next(
            i for i in second_resp.json()["data"]["items"] if i["id"] != first_item["id"]
        )
        assert Decimal(second_resp.json()["data"]["subtotalAmount"]) == Decimal("20.00")

        void_resp = client.post(
            f"/api/v1/orders/{order_id}/items/{first_item['id']}/void", headers=headers
        )
        assert void_resp.status_code == 200, void_resp.text
        voided_order = void_resp.json()["data"]
        assert Decimal(voided_order["subtotalAmount"]) == Decimal("10.00")
        voided_item = next(i for i in voided_order["items"] if i["id"] == first_item["id"])
        assert voided_item["lineStatus"] == "voided"

        fire_resp = client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        assert fire_resp.status_code == 200, fire_resp.text
        fired_item = next(
            i for i in fire_resp.json()["data"]["items"] if i["id"] == second_item["id"]
        )
        assert fired_item["lineStatus"] == "fired"

        void_fired_resp = client.post(
            f"/api/v1/orders/{order_id}/items/{second_item['id']}/void", headers=headers
        )
        assert void_fired_resp.status_code == 409, void_fired_resp.text
        assert void_fired_resp.json()["error"]["code"] == "INVALID_ORDER_ITEM_STATUS_TRANSITION"

    def test_adds_and_refires_an_item_onto_an_already_fired_order(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]

        order_id = client.post(
            f"/api/v1/branches/{branch_id}/orders", headers=headers, json={"orderSource": "pos"}
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 1},
        )

        first_fire = client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        assert first_fire.status_code == 200, first_fire.text
        assert first_fire.json()["data"]["status"] == "fired"

        first_tickets = client.get(
            f"/api/v1/branches/{branch_id}/kitchen-tickets", headers=headers
        ).json()["data"]
        assert len(first_tickets) == 1

        late_item_resp = client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 1},
        )
        assert late_item_resp.status_code == 201, late_item_resp.text
        assert late_item_resp.json()["data"]["status"] == "fired"

        second_fire = client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        assert second_fire.status_code == 200, second_fire.text
        assert all(item["lineStatus"] == "fired" for item in second_fire.json()["data"]["items"])

        second_tickets = client.get(
            f"/api/v1/branches/{branch_id}/kitchen-tickets", headers=headers
        ).json()["data"]
        assert len(second_tickets) == 2

        no_new_items_fire = client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        assert no_new_items_fire.status_code == 409, no_new_items_fire.text
        assert no_new_items_fire.json()["error"]["code"] == "ORDER_HAS_NO_ITEMS"

    def test_fires_kitchen_and_bar_items_into_separate_station_tickets(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]

        order_id = client.post(
            f"/api/v1/branches/{branch_id}/orders", headers=headers, json={"orderSource": "pos"}
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 1},
        )
        client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["bar_menu_item_id"], "quantity": 1},
        )

        fire_resp = client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        assert fire_resp.status_code == 200, fire_resp.text

        tickets_resp = client.get(f"/api/v1/branches/{branch_id}/kitchen-tickets", headers=headers)
        assert tickets_resp.status_code == 200, tickets_resp.text
        tickets = tickets_resp.json()["data"]
        stations = sorted(t["station"] for t in tickets)
        assert stations == ["bar", "kitchen"]
        assert all(len(t["items"]) == 1 for t in tickets)

    def test_serving_an_item_deducts_its_recipe_ingredients_from_inventory(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]

        category_resp = client.post(
            "/api/v1/inventory-categories", headers=headers, json={"name": "Produce"}
        )
        assert category_resp.status_code == 201, category_resp.text
        category_id = category_resp.json()["data"]["id"]

        item_resp = client.post(
            f"/api/v1/branches/{branch_id}/inventory-items",
            headers=headers,
            json={"inventoryCategoryId": category_id, "name": "Beef Patty", "unit": "each"},
        )
        assert item_resp.status_code == 201, item_resp.text
        inventory_item_id = item_resp.json()["data"]["id"]

        receipt_resp = client.post(
            f"/api/v1/inventory-items/{inventory_item_id}/stock-movements",
            headers=headers,
            json={
                "movementType": "adjustment",
                "quantityDelta": "50",
                "reason": "initial stock",
                "approvedByUserId": owner["user_id"],
            },
        )
        assert receipt_resp.status_code == 201, receipt_resp.text

        recipe_resp = client.put(
            f"/api/v1/menu-items/{owner['menu_item_id']}/recipe",
            headers=headers,
            json={
                "name": "Burger recipe",
                "ingredients": [
                    {"inventoryItemId": inventory_item_id, "quantity": "2", "unit": "each"}
                ],
            },
        )
        assert recipe_resp.status_code == 201, recipe_resp.text

        order_id = client.post(
            f"/api/v1/branches/{branch_id}/orders", headers=headers, json={"orderSource": "pos"}
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 3},
        )
        fire_resp = client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        assert fire_resp.status_code == 200, fire_resp.text
        ticket_id = client.get(
            f"/api/v1/branches/{branch_id}/kitchen-tickets", headers=headers
        ).json()["data"][0]["id"]

        client.post(
            f"/api/v1/kitchen-tickets/{ticket_id}/status",
            headers=headers,
            json={"status": "in_progress"},
        )
        client.post(
            f"/api/v1/kitchen-tickets/{ticket_id}/status", headers=headers, json={"status": "ready"}
        )
        served_resp = client.post(
            f"/api/v1/kitchen-tickets/{ticket_id}/status",
            headers=headers,
            json={"status": "served"},
        )
        assert served_resp.status_code == 200, served_resp.text

        after_serve = client.get(
            f"/api/v1/branches/{branch_id}/inventory-items/{inventory_item_id}", headers=headers
        )
        assert after_serve.status_code == 200
        # 2 units/serving * 3 servings ordered = 6 deducted from 50.
        assert Decimal(after_serve.json()["data"]["quantityOnHand"]) == Decimal(44)

        movements_resp = client.get(
            f"/api/v1/inventory-items/{inventory_item_id}/stock-movements", headers=headers
        )
        assert movements_resp.status_code == 200
        movements = movements_resp.json()["data"]
        deduction = next(m for m in movements if m["movementType"] == "sale_deduction")
        assert Decimal(deduction["quantityDelta"]) == Decimal(-6)
        assert deduction["referenceType"] == "order_item"

    def test_opening_and_closing_a_table_order_cascades_table_status(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]
        table_id = owner["table_id"]

        before = client.get(f"/api/v1/branches/{branch_id}/tables/{table_id}", headers=headers)
        assert before.status_code == 200
        assert before.json()["data"]["status"] == "available"

        order_id = client.post(
            f"/api/v1/branches/{branch_id}/orders",
            headers=headers,
            json={"orderSource": "pos", "tableId": table_id},
        ).json()["data"]["id"]

        after_open = client.get(f"/api/v1/branches/{branch_id}/tables/{table_id}", headers=headers)
        assert after_open.json()["data"]["status"] == "occupied"

        client.post(
            f"/api/v1/orders/{order_id}/items",
            headers=headers,
            json={"menuItemId": owner["menu_item_id"], "quantity": 1},
        )
        client.post(f"/api/v1/orders/{order_id}/fire", headers=headers)
        close_resp = client.post(f"/api/v1/orders/{order_id}/close", headers=headers)
        assert close_resp.status_code == 200, close_resp.text

        after_close = client.get(f"/api/v1/branches/{branch_id}/tables/{table_id}", headers=headers)
        assert after_close.json()["data"]["status"] == "available"

    def test_voiding_a_table_order_marks_the_table_available_again(
        self, client: TestClient, owner: dict
    ) -> None:
        headers = _auth_headers(owner["token"])
        branch_id = owner["branch_id"]
        table_id = owner["table_id"]

        order_id = client.post(
            f"/api/v1/branches/{branch_id}/orders",
            headers=headers,
            json={"orderSource": "pos", "tableId": table_id},
        ).json()["data"]["id"]
        assert (
            client.get(f"/api/v1/branches/{branch_id}/tables/{table_id}", headers=headers).json()[
                "data"
            ]["status"]
            == "occupied"
        )

        void_resp = client.post(f"/api/v1/orders/{order_id}/void", headers=headers)
        assert void_resp.status_code == 200, void_resp.text

        after_void = client.get(f"/api/v1/branches/{branch_id}/tables/{table_id}", headers=headers)
        assert after_void.json()["data"]["status"] == "available"

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
