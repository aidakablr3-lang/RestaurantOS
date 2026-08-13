"""End-to-end HTTP integration tests for the guest QR ordering routes
(guest ordering gap fix) against real PostgreSQL.

No auth token anywhere in this file -- every request goes straight to
``/api/v1/qr/{token}/...`` with no ``Authorization`` header, proving the
whole flow (scan -> menu -> create order -> add item -> submit -> poll
status) works for a genuinely unauthenticated caller, the same way
``test_qr_resolution_router.py`` proves it for the bootstrap lookup
alone. Rate-limit assertions import ``GuestOrderRateLimiter``'s own
module-private threshold constants rather than duplicating numbers that
could drift.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import text

from restaurant_os_api.core.ids import generate_qr_token, generate_ulid
from restaurant_os_api.main import create_app
from restaurant_os_api.modules.identity.presentation.dependencies import get_session_factory
from restaurant_os_api.modules.restaurant.domain.entities import QRCode, QRCodeStatus
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyQRCodeRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.rate_limiting.guest_order_limiter import (
    _IP_LIMIT,
    _TOKEN_LIMIT,
    _window_start,
)
from restaurant_os_api.platform.tenancy import TenantContext


def _client_for(session_factory, *, ip: str = "203.0.113.10") -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    return TestClient(app, client=(ip, 12345))


async def _seed_menu(session_factory, *, tenant_id: str) -> dict[str, str]:
    """Seeds Restaurant -> Branch -> MenuCategory -> (available + unavailable)
    MenuItem -> TableZone -> Table via raw SQL, mirroring
    ``test_order_kitchen_billing_payment_router.py``'s own ``_seed_menu``
    convention."""
    restaurant_id = generate_ulid()
    branch_id = generate_ulid()
    category_id = generate_ulid()
    item_id = generate_ulid()
    unavailable_item_id = generate_ulid()
    table_zone_id = generate_ulid()
    table_id = generate_ulid()
    other_table_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO tenants (id, legal_name, display_name, tenant_tier, status, "
                "default_currency_code) VALUES (:id, :name, :name, 'shared', 'active', 'USD') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tenant_id, "name": f"Seed tenant {tenant_id}"},
        )
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
                "currency_code, is_available) VALUES (:id, :tenant_id, :category_id, 'Burger', "
                "10.00, 'USD', true)"
            ),
            {"id": item_id, "tenant_id": tenant_id, "category_id": category_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO menu_items (id, tenant_id, menu_category_id, name, price_amount, "
                "currency_code, is_available) VALUES (:id, :tenant_id, :category_id, "
                "'86d Item', 5.00, 'USD', false)"
            ),
            {"id": unavailable_item_id, "tenant_id": tenant_id, "category_id": category_id},
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
        await uow.session.execute(
            text(
                "INSERT INTO tables (id, tenant_id, branch_id, table_zone_id, table_number, "
                "capacity) VALUES (:id, :tenant_id, :branch_id, :table_zone_id, '13', 4)"
            ),
            {
                "id": other_table_id,
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "table_zone_id": table_zone_id,
            },
        )
    return {
        "tenant_id": tenant_id,
        "restaurant_id": restaurant_id,
        "branch_id": branch_id,
        "category_id": category_id,
        "menu_item_id": item_id,
        "unavailable_item_id": unavailable_item_id,
        "table_id": table_id,
        "other_table_id": other_table_id,
    }


async def _seed_qr_code(
    session_factory,
    seeded: dict[str, str],
    *,
    table_id: str | None = None,
    status: QRCodeStatus = QRCodeStatus.ACTIVE,
) -> QRCode:
    async with UnitOfWork(session_factory, TenantContext(seeded["tenant_id"])) as uow:
        return await SQLAlchemyQRCodeRepository(uow.session).create(
            QRCode(
                id=generate_ulid(),
                tenant_id=seeded["tenant_id"],
                branch_id=seeded["branch_id"],
                table_id=table_id or seeded["table_id"],
                token=generate_qr_token(),
                status=status,
                created_at=datetime.now(UTC),
            )
        )


class TestGuestOrderingFullFlow:
    async def test_scan_menu_order_add_item_submit_and_poll_status(self, session_factory) -> None:
        seeded = await _seed_menu(session_factory, tenant_id=generate_ulid())
        qr = await _seed_qr_code(session_factory, seeded)
        client = _client_for(session_factory)

        menu_response = client.get(f"/api/v1/qr/{qr.token}/menu")
        assert menu_response.status_code == 200, menu_response.text
        menu_body = menu_response.json()["data"]
        assert menu_body["branchId"] == seeded["branch_id"]
        assert menu_body["tableId"] == seeded["table_id"]
        assert menu_body["restaurantName"] == "R"
        assert menu_body["branchName"] == "Downtown"
        assert menu_body["tableNumber"] == "12"
        item_ids = [item["id"] for cat in menu_body["categories"] for item in cat["items"]]
        assert item_ids == [seeded["menu_item_id"]]

        create_response = client.post(f"/api/v1/qr/{qr.token}/orders")
        assert create_response.status_code == 201, create_response.text
        order = create_response.json()["data"]
        assert order["status"] == "open"
        assert order["orderSource"] == "qr"
        assert order["tableId"] == seeded["table_id"]
        order_id = order["id"]

        add_item_response = client.post(
            f"/api/v1/qr/{qr.token}/orders/{order_id}/items",
            json={"menuItemId": seeded["menu_item_id"], "quantity": 2},
        )
        assert add_item_response.status_code == 201, add_item_response.text
        after_add = add_item_response.json()["data"]
        assert after_add["subtotalAmount"] == "20.0000"
        assert len(after_add["items"]) == 1

        submit_response = client.post(f"/api/v1/qr/{qr.token}/orders/{order_id}/submit")
        assert submit_response.status_code == 200, submit_response.text
        fired = submit_response.json()["data"]
        assert fired["status"] == "fired"
        assert fired["items"][0]["lineStatus"] == "fired"

        status_response = client.get(f"/api/v1/qr/{qr.token}/orders/{order_id}")
        assert status_response.status_code == 200, status_response.text
        assert status_response.json()["data"]["status"] == "fired"

    async def test_unavailable_items_do_not_appear_on_the_guest_menu(self, session_factory) -> None:
        seeded = await _seed_menu(session_factory, tenant_id=generate_ulid())
        qr = await _seed_qr_code(session_factory, seeded)

        response = _client_for(session_factory).get(f"/api/v1/qr/{qr.token}/menu")

        item_ids = [
            item["id"] for cat in response.json()["data"]["categories"] for item in cat["items"]
        ]
        assert seeded["unavailable_item_id"] not in item_ids

    async def test_no_authentication_is_required_anywhere_in_the_flow(
        self, session_factory
    ) -> None:
        seeded = await _seed_menu(session_factory, tenant_id=generate_ulid())
        qr = await _seed_qr_code(session_factory, seeded)
        client = _client_for(session_factory)

        # Deliberately no Authorization header on any call.
        assert client.get(f"/api/v1/qr/{qr.token}/menu").status_code == 200
        order_id = client.post(f"/api/v1/qr/{qr.token}/orders").json()["data"]["id"]
        assert client.get(f"/api/v1/qr/{qr.token}/orders/{order_id}").status_code == 200


class TestGuestOrderingTokenResolutionFailures:
    async def test_a_revoked_token_returns_not_found_for_the_menu_route(
        self, session_factory
    ) -> None:
        seeded = await _seed_menu(session_factory, tenant_id=generate_ulid())
        qr = await _seed_qr_code(session_factory, seeded, status=QRCodeStatus.REVOKED)

        response = _client_for(session_factory).get(f"/api/v1/qr/{qr.token}/menu")

        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}

    async def test_a_nonexistent_token_returns_not_found_for_order_creation(
        self, session_factory
    ) -> None:
        response = _client_for(session_factory).post("/api/v1/qr/no-such-token/orders")

        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}


class TestGuestOrderingTableIsolation:
    async def test_a_guest_cannot_add_items_to_an_order_from_a_different_table(
        self, session_factory
    ) -> None:
        seeded = await _seed_menu(session_factory, tenant_id=generate_ulid())
        qr_table_a = await _seed_qr_code(session_factory, seeded, table_id=seeded["table_id"])
        qr_table_b = await _seed_qr_code(session_factory, seeded, table_id=seeded["other_table_id"])
        client = _client_for(session_factory)

        order_id = client.post(f"/api/v1/qr/{qr_table_a.token}/orders").json()["data"]["id"]

        response = client.post(
            f"/api/v1/qr/{qr_table_b.token}/orders/{order_id}/items",
            json={"menuItemId": seeded["menu_item_id"], "quantity": 1},
        )

        assert response.status_code == 404

    async def test_a_guest_cannot_poll_an_order_from_a_different_table(
        self, session_factory
    ) -> None:
        seeded = await _seed_menu(session_factory, tenant_id=generate_ulid())
        qr_table_a = await _seed_qr_code(session_factory, seeded, table_id=seeded["table_id"])
        qr_table_b = await _seed_qr_code(session_factory, seeded, table_id=seeded["other_table_id"])
        client = _client_for(session_factory)

        order_id = client.post(f"/api/v1/qr/{qr_table_a.token}/orders").json()["data"]["id"]

        response = client.get(f"/api/v1/qr/{qr_table_b.token}/orders/{order_id}")

        assert response.status_code == 404


class TestGuestOrderingRateLimit:
    async def test_exhausting_the_ip_limit_blocks_further_guest_order_calls(
        self, session_factory
    ) -> None:
        seeded = await _seed_menu(session_factory, tenant_id=generate_ulid())
        qr = await _seed_qr_code(session_factory, seeded)
        ip = "198.51.100.201"
        window_start = _window_start(datetime.now(UTC))
        async with UnitOfWork(session_factory) as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO qr_resolution_rate_limits "
                    "(id, bucket_type, bucket_key, window_start, total_count, failed_count) "
                    "VALUES (:id, 'ip', :bucket_key, :window_start, :total_count, 0)"
                ),
                {
                    "id": generate_ulid(),
                    "bucket_key": f"order:{ip}",
                    "window_start": window_start,
                    "total_count": _IP_LIMIT,
                },
            )

        response = _client_for(session_factory, ip=ip).get(f"/api/v1/qr/{qr.token}/menu")

        assert response.status_code == 429
        assert response.json() == {"error": "rate_limited"}

    async def test_exhausting_the_token_limit_blocks_further_calls_for_that_token_only(
        self, session_factory
    ) -> None:
        seeded = await _seed_menu(session_factory, tenant_id=generate_ulid())
        qr_a = await _seed_qr_code(session_factory, seeded)
        qr_b = await _seed_qr_code(session_factory, seeded)
        window_start = _window_start(datetime.now(UTC))
        async with UnitOfWork(session_factory) as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO qr_resolution_rate_limits "
                    "(id, bucket_type, bucket_key, window_start, total_count, failed_count) "
                    "VALUES (:id, 'token', :bucket_key, :window_start, :total_count, 0)"
                ),
                {
                    "id": generate_ulid(),
                    "bucket_key": f"order:{qr_a.token}",
                    "window_start": window_start,
                    "total_count": _TOKEN_LIMIT,
                },
            )

        blocked_client = _client_for(session_factory, ip="198.51.100.210")
        blocked_response = blocked_client.get(f"/api/v1/qr/{qr_a.token}/menu")
        assert blocked_response.status_code == 429

        other_response = blocked_client.get(f"/api/v1/qr/{qr_b.token}/menu")
        assert other_response.status_code == 200

    async def test_qr_resolution_and_guest_order_rate_limits_are_isolated_namespaces(
        self, session_factory
    ) -> None:
        """Exhausting the strict QR-*resolution* budget for an IP must
        not block that same IP's guest-*order* calls -- the two limiters
        use disjoint ``bucket_key`` namespaces on purpose (see
        ``GuestResolveQRCodeUseCase``'s own docstring)."""
        seeded = await _seed_menu(session_factory, tenant_id=generate_ulid())
        qr = await _seed_qr_code(session_factory, seeded)
        ip = "198.51.100.220"
        window_start = _window_start(datetime.now(UTC))
        async with UnitOfWork(session_factory) as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO qr_resolution_rate_limits "
                    "(id, bucket_type, bucket_key, window_start, total_count, failed_count) "
                    "VALUES (:id, 'ip', :bucket_key, :window_start, 999, 0)"
                ),
                {"id": generate_ulid(), "bucket_key": ip, "window_start": window_start},
            )

        response = _client_for(session_factory, ip=ip).get(f"/api/v1/qr/{qr.token}/menu")

        assert response.status_code == 200
