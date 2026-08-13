"""End-to-end HTTP tests for Reservation CRUD against a real
PostgreSQL instance (Sprint 5 Step 4.11) -- the final implementation
step required to complete the currently-defined Restaurant Platform
backend.

Follows test_table_router.py's exact pattern. All three routes are
nested under branch_id, gated by reservation.manage/reservation.read
via require_branch_permission -- Reservation gets no separate flat
status-change route, so PATCH alone carries both plain field edits and
status transitions, routed through the domain's own transition methods
(never a direct status assignment) -- see update_reservation.py's own
docstring.
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
REQUESTED_AT = "2026-06-01T19:00:00Z"


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
    """A user holding reservation.read/manage/table.manage/branch.manage/
    restaurant.manage tenant-wide."""
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        permission_codes=frozenset(
            {
                "reservation.read",
                "reservation.manage",
                "table.read",
                "table.manage",
                "branch.manage",
                "restaurant.manage",
            }
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
async def table_zone(client: TestClient, owner: dict, branch: dict) -> dict:
    response = client.post(
        f"/api/v1/branches/{branch['id']}/table-zones",
        headers=_auth_headers(owner["token"]),
        json={"name": "Patio"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest_asyncio.fixture
async def table(client: TestClient, owner: dict, branch: dict, table_zone: dict) -> dict:
    response = client.post(
        f"/api/v1/branches/{branch['id']}/tables",
        headers=_auth_headers(owner["token"]),
        json={"tableZoneId": table_zone["id"], "tableNumber": "12A", "capacity": 4},
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
        permission_codes=frozenset({"reservation.read"}),
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
    body = {"partySize": 4, "requestedAt": REQUESTED_AT}
    body.update(overrides)
    return body


def _create_reservation(client: TestClient, owner: dict, branch_id: str, **overrides) -> dict:
    response = client.post(
        f"/api/v1/branches/{branch_id}/reservations",
        headers=_auth_headers(owner["token"]),
        json=_create_body(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestCreateReservation:
    def test_a_manage_holder_can_create_a_reservation(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/reservations",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["partySize"] == 4
        assert data["status"] == "requested"
        assert data["branchId"] == branch["id"]
        assert data["tenantId"] == owner["tenant_id"]
        assert data["tableId"] is None
        assert data["customerId"] is None

    def test_can_create_with_a_table_assigned(
        self, client: TestClient, owner: dict, branch: dict, table: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/reservations",
            headers=_auth_headers(owner["token"]),
            json=_create_body(tableId=table["id"]),
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["tableId"] == table["id"]

    def test_an_unknown_branch_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            f"/api/v1/branches/{'0' * 26}/reservations",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_an_unknown_table_id_is_404(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/reservations",
            headers=_auth_headers(owner["token"]),
            json=_create_body(tableId="0" * 26),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    async def test_a_table_belonging_to_a_different_branch_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict, table: dict
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]

        response = client.post(
            f"/api/v1/branches/{other_branch['id']}/reservations",
            headers=_auth_headers(owner["token"]),
            json=_create_body(tableId=table["id"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    async def test_a_branch_belonging_to_another_tenant_is_404_not_a_leak(
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
            permission_codes=frozenset({"restaurant.manage", "branch.manage"}),
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

        response = client.post(
            f"/api/v1/branches/{other_branch['id']}/reservations",
            headers=_auth_headers(owner["token"]),
            json=_create_body(),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, branch: dict) -> None:
        response = client.post(f"/api/v1/branches/{branch['id']}/reservations", json=_create_body())
        assert response.status_code == 401

    def test_denied_without_reservation_manage(
        self, client: TestClient, reader_only: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/reservations",
            headers=_auth_headers(reader_only["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/reservations",
            headers=_auth_headers(no_permission["token"]),
            json=_create_body(),
        )
        assert response.status_code == 403

    async def test_a_branch_scoped_manage_grant_can_create_in_its_own_branch(
        self, client: TestClient, owner: dict, branch: dict, session_factory
    ) -> None:
        email = "branchmgr@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"reservation.read", "reservation.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/branches/{branch['id']}/reservations",
            headers=_auth_headers(token),
            json=_create_body(),
        )
        assert response.status_code == 201, response.text

    async def test_a_branch_scoped_manage_grant_cannot_create_in_a_different_branch(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict, session_factory
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
            permission_codes=frozenset({"reservation.read", "reservation.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/branches/{other_branch['id']}/reservations",
            headers=_auth_headers(token),
            json=_create_body(),
        )
        assert response.status_code == 403

    def test_zero_party_size_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/reservations",
            headers=_auth_headers(owner["token"]),
            json=_create_body(partySize=0),
        )
        assert response.status_code == 422

    def test_missing_required_field_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.post(
            f"/api/v1/branches/{branch['id']}/reservations",
            headers=_auth_headers(owner["token"]),
            json={},
        )
        assert response.status_code == 422


class TestCreateReservationIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/reservations"
        body = _create_body()

        first = client.post(url, headers=headers, json=body)
        second = client.post(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()

        list_response = client.get(url, headers=_auth_headers(owner["token"]))
        assert list_response.json()["meta"]["total"] == 1

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/reservations"

        first = client.post(url, headers=headers, json=_create_body(partySize=2))
        assert first.status_code == 201, first.text

        second = client.post(url, headers=headers, json=_create_body(partySize=6))
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestGetReservation:
    def test_a_read_holder_can_get_a_reservation(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        response = client.get(
            f"/api/v1/branches/{branch['id']}/reservations/{reservation['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] == reservation["id"]

    def test_unknown_id_returns_404(self, client: TestClient, owner: dict, branch: dict) -> None:
        response = client.get(
            f"/api/v1/branches/{branch['id']}/reservations/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESERVATION_NOT_FOUND"

    async def test_a_reservation_belonging_to_a_different_branch_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        other_reservation = _create_reservation(client, owner, other_branch["id"])

        response = client.get(
            f"/api/v1/branches/{branch['id']}/reservations/{other_reservation['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESERVATION_NOT_FOUND"

    async def test_a_reservation_in_another_tenant_is_a_404_not_a_403(
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
            permission_codes=frozenset(
                {"restaurant.manage", "branch.manage", "reservation.manage"}
            ),
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
        other_reservation = client.post(
            f"/api/v1/branches/{other_branch['id']}/reservations",
            headers=_auth_headers(other_token),
            json=_create_body(),
        ).json()["data"]

        response = client.get(
            f"/api/v1/branches/{branch['id']}/reservations/{other_reservation['id']}",
            headers=_auth_headers(owner["token"]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESERVATION_NOT_FOUND"

    async def test_branch_scoped_grant_can_read_its_own_branchs_reservation(
        self, client: TestClient, owner: dict, branch: dict, session_factory
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        email = "branchreader@example.com"

        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"reservation.read"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.get(
            f"/api/v1/branches/{branch['id']}/reservations/{reservation['id']}",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text

    def test_requires_authentication(self, client: TestClient, branch: dict) -> None:
        response = client.get(f"/api/v1/branches/{branch['id']}/reservations/{'0' * 26}")
        assert response.status_code == 401


class TestListReservations:
    def test_lists_only_the_requested_branchs_reservations(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        for _ in range(3):
            _create_reservation(client, owner, branch["id"])

        response = client.get(
            f"/api/v1/branches/{branch['id']}/reservations", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 3

    def test_pagination_offset_and_limit(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        for _ in range(5):
            _create_reservation(client, owner, branch["id"])

        page_1 = client.get(
            f"/api/v1/branches/{branch['id']}/reservations?offset=0&limit=2",
            headers=_auth_headers(owner["token"]),
        )
        page_2 = client.get(
            f"/api/v1/branches/{branch['id']}/reservations?offset=2&limit=2",
            headers=_auth_headers(owner["token"]),
        )
        assert len(page_1.json()["data"]) == 2
        assert len(page_2.json()["data"]) == 2
        assert page_1.json()["meta"]["total"] == 5
        ids_1 = {r["id"] for r in page_1.json()["data"]}
        ids_2 = {r["id"] for r in page_2.json()["data"]}
        assert ids_1.isdisjoint(ids_2)

    def test_an_unknown_branch_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(
            f"/api/v1/branches/{'0' * 26}/reservations", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, branch: dict) -> None:
        response = client.get(f"/api/v1/branches/{branch['id']}/reservations")
        assert response.status_code == 401

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, branch: dict
    ) -> None:
        response = client.get(
            f"/api/v1/branches/{branch['id']}/reservations",
            headers=_auth_headers(no_permission["token"]),
        )
        assert response.status_code == 403


class TestUpdateReservation:
    def test_a_manage_holder_can_edit_party_size_without_changing_status(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])

        response = client.patch(
            f"/api/v1/branches/{branch['id']}/reservations/{reservation['id']}",
            headers=_auth_headers(owner["token"]),
            json={"partySize": 8, "status": "requested"},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["partySize"] == 8
        assert data["status"] == "requested"

    def test_can_assign_a_table(
        self, client: TestClient, owner: dict, branch: dict, table: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])

        response = client.patch(
            f"/api/v1/branches/{branch['id']}/reservations/{reservation['id']}",
            headers=_auth_headers(owner["token"]),
            json={"partySize": 4, "status": "requested", "tableId": table["id"]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["tableId"] == table["id"]

    async def test_assigning_a_table_from_a_different_branch_is_404(
        self, client: TestClient, owner: dict, restaurant_id: str, branch: dict, table: dict
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        reservation = _create_reservation(client, owner, other_branch["id"])

        response = client.patch(
            f"/api/v1/branches/{other_branch['id']}/reservations/{reservation['id']}",
            headers=_auth_headers(owner["token"]),
            json={"partySize": 4, "status": "requested", "tableId": table["id"]},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    def test_updating_an_unknown_id_returns_404(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.patch(
            f"/api/v1/branches/{branch['id']}/reservations/{'0' * 26}",
            headers=_auth_headers(owner["token"]),
            json={"partySize": 2, "status": "requested"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESERVATION_NOT_FOUND"

    def test_denied_without_reservation_manage(
        self, client: TestClient, owner: dict, reader_only: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        response = client.patch(
            f"/api/v1/branches/{branch['id']}/reservations/{reservation['id']}",
            headers=_auth_headers(reader_only["token"]),
            json={"partySize": 2, "status": "requested"},
        )
        assert response.status_code == 403

    def test_zero_party_size_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        response = client.patch(
            f"/api/v1/branches/{branch['id']}/reservations/{reservation['id']}",
            headers=_auth_headers(owner["token"]),
            json={"partySize": 0, "status": "requested"},
        )
        assert response.status_code == 422

    def test_idempotent_update_replays_on_the_same_key_and_body(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        body = {"partySize": 6, "status": "requested"}
        url = f"/api/v1/branches/{branch['id']}/reservations/{reservation['id']}"

        first = client.patch(url, headers=headers, json=body)
        second = client.patch(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_idempotency_key_conflict_on_a_different_body(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/reservations/{reservation['id']}"

        first = client.patch(url, headers=headers, json={"partySize": 2, "status": "requested"})
        assert first.status_code == 200, first.text

        second = client.patch(url, headers=headers, json={"partySize": 6, "status": "requested"})
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestReservationStatusTransitions:
    def _patch_status(
        self, client: TestClient, owner: dict, branch_id: str, reservation_id: str, status: str
    ):
        return client.patch(
            f"/api/v1/branches/{branch_id}/reservations/{reservation_id}",
            headers=_auth_headers(owner["token"]),
            json={"partySize": 4, "status": status},
        )

    def test_requested_to_confirmed_to_seated_to_completed(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])

        confirmed = self._patch_status(client, owner, branch["id"], reservation["id"], "confirmed")
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["data"]["status"] == "confirmed"

        seated = self._patch_status(client, owner, branch["id"], reservation["id"], "seated")
        assert seated.status_code == 200, seated.text
        assert seated.json()["data"]["status"] == "seated"

        completed = self._patch_status(client, owner, branch["id"], reservation["id"], "completed")
        assert completed.status_code == 200, completed.text
        assert completed.json()["data"]["status"] == "completed"

    def test_requested_to_canceled(self, client: TestClient, owner: dict, branch: dict) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        response = self._patch_status(client, owner, branch["id"], reservation["id"], "canceled")
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "canceled"

    def test_confirmed_to_no_show(self, client: TestClient, owner: dict, branch: dict) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        self._patch_status(client, owner, branch["id"], reservation["id"], "confirmed")
        response = self._patch_status(client, owner, branch["id"], reservation["id"], "no_show")
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "no_show"

    def test_requested_to_seated_directly_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        response = self._patch_status(client, owner, branch["id"], reservation["id"], "seated")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_RESERVATION_STATUS_TRANSITION"

    def test_completed_is_a_terminal_state(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        self._patch_status(client, owner, branch["id"], reservation["id"], "confirmed")
        self._patch_status(client, owner, branch["id"], reservation["id"], "seated")
        self._patch_status(client, owner, branch["id"], reservation["id"], "completed")

        response = self._patch_status(client, owner, branch["id"], reservation["id"], "canceled")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_RESERVATION_STATUS_TRANSITION"

    def test_canceled_is_a_terminal_state(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        self._patch_status(client, owner, branch["id"], reservation["id"], "canceled")

        response = self._patch_status(client, owner, branch["id"], reservation["id"], "confirmed")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_RESERVATION_STATUS_TRANSITION"

    def test_reverting_to_requested_is_always_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        self._patch_status(client, owner, branch["id"], reservation["id"], "confirmed")

        response = self._patch_status(client, owner, branch["id"], reservation["id"], "requested")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_RESERVATION_STATUS_TRANSITION"

    def test_an_invalid_status_value_is_a_422(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        reservation = _create_reservation(client, owner, branch["id"])
        response = self._patch_status(
            client, owner, branch["id"], reservation["id"], "not-a-real-status"
        )
        assert response.status_code == 422
