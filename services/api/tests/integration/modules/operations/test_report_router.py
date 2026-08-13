"""End-to-end HTTP integration tests for the End-of-Day report route
(full-day operational simulation gap fix) against real PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime

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


def _token_service() -> JWTTokenService:
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


def _client_for(session_factory) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    token_service = _token_service()
    app.dependency_overrides[get_token_service] = lambda: token_service
    return TestClient(app)


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
) -> None:
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
        await user_role_repo.create(
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


async def _seed_branch(session_factory, *, tenant_id: str) -> dict[str, str]:
    restaurant_id = generate_ulid()
    branch_id = generate_ulid()
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
    return {"restaurant_id": restaurant_id, "branch_id": branch_id}


async def _seed_order_with_payment(
    session_factory,
    *,
    tenant_id: str,
    branch_id: str,
    opened_at: datetime,
    payment_created_at: datetime,
) -> None:
    order_id = generate_ulid()
    bill_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO orders (id, tenant_id, branch_id, order_source, status, "
                "subtotal_amount, tax_amount, currency_code, opened_at) "
                "VALUES (:id, :tenant_id, :branch_id, 'pos', 'served', 20.00, 2.00, 'USD', "
                ":opened_at)"
            ),
            {
                "id": order_id,
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "opened_at": opened_at,
            },
        )
        await uow.session.execute(
            text(
                "INSERT INTO bills (id, tenant_id, branch_id, status, order_id) "
                "VALUES (:id, :tenant_id, :branch_id, 'closed', :order_id)"
            ),
            {"id": bill_id, "tenant_id": tenant_id, "branch_id": branch_id, "order_id": order_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO payments (id, tenant_id, branch_id, bill_id, tender_type, amount, "
                "currency_code, tip_amount, status, created_at) VALUES (:id, :tenant_id, "
                ":branch_id, :bill_id, 'cash', 22.00, 'USD', 3.00, 'settled', :created_at)"
            ),
            {
                "id": generate_ulid(),
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "bill_id": bill_id,
                "created_at": payment_created_at,
            },
        )


class TestEndOfDayReport:
    async def test_a_reports_read_holder_gets_the_full_report(self, session_factory) -> None:
        tenant_id = generate_ulid()
        seeded = await _seed_branch(session_factory, tenant_id=tenant_id)
        report_moment = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
        await _seed_order_with_payment(
            session_factory,
            tenant_id=tenant_id,
            branch_id=seeded["branch_id"],
            opened_at=report_moment,
            payment_created_at=report_moment,
        )
        user_id = await _seed_user(session_factory, tenant_id=tenant_id, email="owner@example.com")
        await _grant_role(
            session_factory,
            tenant_id=tenant_id,
            user_id=user_id,
            permission_codes=frozenset({"reports.read"}),
        )
        client_ = _client_for(session_factory)
        token = _login_sync(client_, tenant_id=tenant_id, email="owner@example.com")

        response = client_.get(
            f"/api/v1/branches/{seeded['branch_id']}/reports/end-of-day",
            params={"date": "2026-08-12"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["branchId"] == seeded["branch_id"]
        assert data["reportDate"] == "2026-08-12"
        assert data["currencyCode"] == "USD"
        assert data["orderCount"] == 1
        assert data["grossSalesAmount"] == "22.0000"
        assert data["totalCollectedAmount"] == "22.0000"
        assert data["totalTipsAmount"] == "3.0000"
        assert data["tenderBreakdown"] == [
            {"tenderType": "cash", "amount": "22.0000", "paymentCount": 1}
        ]

    async def test_orders_from_a_different_day_are_excluded(self, session_factory) -> None:
        tenant_id = generate_ulid()
        seeded = await _seed_branch(session_factory, tenant_id=tenant_id)
        yesterday = datetime(2026, 8, 11, 23, 0, tzinfo=UTC)
        await _seed_order_with_payment(
            session_factory,
            tenant_id=tenant_id,
            branch_id=seeded["branch_id"],
            opened_at=yesterday,
            payment_created_at=yesterday,
        )
        user_id = await _seed_user(session_factory, tenant_id=tenant_id, email="owner2@example.com")
        await _grant_role(
            session_factory,
            tenant_id=tenant_id,
            user_id=user_id,
            permission_codes=frozenset({"reports.read"}),
        )
        client_ = _client_for(session_factory)
        token = _login_sync(client_, tenant_id=tenant_id, email="owner2@example.com")

        response = client_.get(
            f"/api/v1/branches/{seeded['branch_id']}/reports/end-of-day",
            params={"date": "2026-08-12"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["orderCount"] == 0
        assert data["grossSalesAmount"] == "0"

    async def test_a_user_without_reports_read_is_denied(self, session_factory) -> None:
        tenant_id = generate_ulid()
        seeded = await _seed_branch(session_factory, tenant_id=tenant_id)
        user_id = await _seed_user(session_factory, tenant_id=tenant_id, email="waiter@example.com")
        await _grant_role(
            session_factory,
            tenant_id=tenant_id,
            user_id=user_id,
            permission_codes=frozenset({"order.read"}),
        )
        client_ = _client_for(session_factory)
        token = _login_sync(client_, tenant_id=tenant_id, email="waiter@example.com")

        response = client_.get(
            f"/api/v1/branches/{seeded['branch_id']}/reports/end-of-day",
            params={"date": "2026-08-12"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    async def test_requires_authentication(self, session_factory) -> None:
        tenant_id = generate_ulid()
        seeded = await _seed_branch(session_factory, tenant_id=tenant_id)
        client_ = _client_for(session_factory)

        response = client_.get(
            f"/api/v1/branches/{seeded['branch_id']}/reports/end-of-day",
            params={"date": "2026-08-12"},
        )

        assert response.status_code == 401
