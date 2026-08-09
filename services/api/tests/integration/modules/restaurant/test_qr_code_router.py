"""End-to-end HTTP tests for QR Code management against a real
PostgreSQL instance (Sprint 5 Step 4.6).

Scoped to the authenticated management routes only
(``POST``/``GET /api/v1/tables/{id}/qr-codes``) -- both deliberately
flat paths per Architecture SS7, gated by the coarse
``require_permission_at_any_scope`` plus
``resolve_and_authorize_branch``'s fine-grained check, same as the
Table status-change route (Step 4.5). The unauthenticated resolution
endpoint (``GET /api/v1/qr/{token}``), added in Step 4.7, has its own
dedicated file, ``test_qr_resolution_router.py`` -- this file only
confirms the two route groups stay isolated from each other.
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
from restaurant_os_api.modules.restaurant.domain.entities import QRCode, QRCodeStatus
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyQRCodeRepository,
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
    is_active: bool = True,
) -> str:
    """Returns the created UserRole's id so a test can revoke it."""
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
                branch_id=branch_id,
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
    """A user holding table.read/table.manage/branch.manage tenant-wide."""
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        permission_codes=frozenset(
            {"table.read", "table.manage", "branch.manage", "restaurant.read"}
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
        permission_codes=frozenset({"table.read"}),
    )
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def no_permission(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    email = "noperm@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


def _generate_qr_code(client: TestClient, owner: dict, table_id: str) -> dict:
    response = client.post(
        f"/api/v1/tables/{table_id}/qr-codes", headers=_auth_headers(owner["token"])
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestCreateQRCode:
    def test_a_manage_holder_can_generate_a_qr_code(
        self, client: TestClient, owner: dict, table: dict
    ) -> None:
        response = client.post(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["status"] == "active"
        assert data["tableId"] == table["id"]
        assert data["branchId"] == table["branchId"]
        assert data["tenantId"] == owner["tenant_id"]
        assert len(data["token"]) > 26
        assert data["token"] != data["id"]

    def test_regenerating_revokes_the_previous_active_code(
        self, client: TestClient, owner: dict, table: dict
    ) -> None:
        first = _generate_qr_code(client, owner, table["id"])
        second = _generate_qr_code(client, owner, table["id"])

        assert second["id"] != first["id"]
        assert second["token"] != first["token"]
        assert second["status"] == "active"

        history = client.get(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(owner["token"])
        ).json()["data"]
        by_id = {c["id"]: c for c in history}
        assert by_id[first["id"]]["status"] == "revoked"
        assert by_id[second["id"]]["status"] == "active"

    def test_three_generations_leave_exactly_one_active_code(
        self, client: TestClient, owner: dict, table: dict
    ) -> None:
        codes = [_generate_qr_code(client, owner, table["id"]) for _ in range(3)]

        history = client.get(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(owner["token"])
        ).json()["data"]
        assert len(history) == 3
        active = [c for c in history if c["status"] == "active"]
        revoked = [c for c in history if c["status"] == "revoked"]
        assert len(active) == 1
        assert len(revoked) == 2
        assert active[0]["id"] == codes[-1]["id"]

    def test_an_unknown_table_id_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.post(
            f"/api/v1/tables/{'0' * 26}/qr-codes", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    async def test_a_table_in_another_tenant_is_404_not_a_leak(
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
            permission_codes=frozenset({"restaurant.manage", "branch.manage", "table.manage"}),
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
        other_zone = client.post(
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(other_token),
            json={"name": "Zone"},
        ).json()["data"]
        other_table = client.post(
            f"/api/v1/branches/{other_branch['id']}/tables",
            headers=_auth_headers(other_token),
            json={"tableZoneId": other_zone["id"], "tableNumber": "1", "capacity": 2},
        ).json()["data"]

        response = client.post(
            f"/api/v1/tables/{other_table['id']}/qr-codes", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, table: dict) -> None:
        response = client.post(f"/api/v1/tables/{table['id']}/qr-codes")
        assert response.status_code == 401

    def test_denied_without_table_manage(
        self, client: TestClient, reader_only: dict, table: dict
    ) -> None:
        response = client.post(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(reader_only["token"])
        )
        assert response.status_code == 403

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, table: dict
    ) -> None:
        response = client.post(
            f"/api/v1/tables/{table['id']}/qr-codes",
            headers=_auth_headers(no_permission["token"]),
        )
        assert response.status_code == 403

    async def test_denied_when_the_only_grant_is_on_an_inactive_role(
        self, client: TestClient, owner: dict, table: dict, session_factory
    ) -> None:
        email = "inactive@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
            is_active=False,
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(token)
        )
        assert response.status_code == 403

    async def test_denied_once_the_grant_is_revoked(
        self, client: TestClient, owner: dict, table: dict, session_factory
    ) -> None:
        email = "revoked@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        user_role_id = await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
        first = client.post(f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(token))
        assert first.status_code == 201, first.text

        await _revoke_role(session_factory, tenant_id=owner["tenant_id"], user_role_id=user_role_id)

        second = client.post(f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(token))
        assert second.status_code == 403

    async def test_a_branch_scoped_manage_holder_can_generate_at_their_own_branch(
        self, client: TestClient, owner: dict, branch: dict, table: dict, session_factory
    ) -> None:
        email = "branchmgr@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(token)
        )
        assert response.status_code == 201, response.text

    async def test_a_branch_scoped_manage_holder_cannot_generate_at_a_different_branch(
        self,
        client: TestClient,
        owner: dict,
        restaurant_id: str,
        branch: dict,
        table: dict,
        session_factory,
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        other_zone = client.post(
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json={"name": "Bar"},
        ).json()["data"]
        other_table = client.post(
            f"/api/v1/branches/{other_branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json={"tableZoneId": other_zone["id"], "tableNumber": "1", "capacity": 2},
        ).json()["data"]

        email = "scoped@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read", "table.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.post(
            f"/api/v1/tables/{other_table['id']}/qr-codes", headers=_auth_headers(token)
        )
        assert response.status_code == 403


class TestCreateQRCodeIdempotency:
    def test_the_same_key_replays_the_original_response(
        self, client: TestClient, owner: dict, table: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/tables/{table['id']}/qr-codes"

        first = client.post(url, headers=headers)
        second = client.post(url, headers=headers)

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()

        history = client.get(url, headers=_auth_headers(owner["token"])).json()["data"]
        assert len(history) == 1

    def test_the_same_key_against_a_different_table_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, branch: dict, table_zone: dict, table: dict
    ) -> None:
        other_table = client.post(
            f"/api/v1/branches/{branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json={"tableZoneId": table_zone["id"], "tableNumber": "99", "capacity": 2},
        ).json()["data"]

        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}

        first = client.post(f"/api/v1/tables/{table['id']}/qr-codes", headers=headers)
        assert first.status_code == 201, first.text

        second = client.post(f"/api/v1/tables/{other_table['id']}/qr-codes", headers=headers)
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


class TestListQRCodes:
    def test_a_read_holder_can_list_history(
        self, client: TestClient, owner: dict, table: dict
    ) -> None:
        code = _generate_qr_code(client, owner, table["id"])
        response = client.get(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"][0]["id"] == code["id"]

    def test_ordered_newest_first(self, client: TestClient, owner: dict, table: dict) -> None:
        first = _generate_qr_code(client, owner, table["id"])
        second = _generate_qr_code(client, owner, table["id"])

        response = client.get(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(owner["token"])
        )
        ids = [c["id"] for c in response.json()["data"]]
        assert ids == [second["id"], first["id"]]

    def test_empty_history_for_a_table_with_no_codes(
        self, client: TestClient, owner: dict, table: dict
    ) -> None:
        response = client.get(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_an_unknown_table_is_404(self, client: TestClient, owner: dict) -> None:
        response = client.get(
            f"/api/v1/tables/{'0' * 26}/qr-codes", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    async def test_a_table_in_another_tenant_is_404_not_a_leak(
        self, client: TestClient, owner: dict, session_factory
    ) -> None:
        other_tenant_id = generate_ulid()
        other_email = "other2@example.com"
        other_user_id = await _seed_user(
            session_factory, tenant_id=other_tenant_id, email=other_email
        )
        await _grant_role(
            session_factory,
            tenant_id=other_tenant_id,
            user_id=other_user_id,
            permission_codes=frozenset({"restaurant.manage", "branch.manage", "table.manage"}),
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
        other_zone = client.post(
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(other_token),
            json={"name": "Zone"},
        ).json()["data"]
        other_table = client.post(
            f"/api/v1/branches/{other_branch['id']}/tables",
            headers=_auth_headers(other_token),
            json={"tableZoneId": other_zone["id"], "tableNumber": "1", "capacity": 2},
        ).json()["data"]

        response = client.get(
            f"/api/v1/tables/{other_table['id']}/qr-codes", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TABLE_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, table: dict) -> None:
        response = client.get(f"/api/v1/tables/{table['id']}/qr-codes")
        assert response.status_code == 401

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, table: dict
    ) -> None:
        response = client.get(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(no_permission["token"])
        )
        assert response.status_code == 403

    async def test_a_branch_scoped_read_holder_can_list_their_own_branchs_history(
        self, client: TestClient, owner: dict, branch: dict, table: dict, session_factory
    ) -> None:
        email = "branchreader@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.get(
            f"/api/v1/tables/{table['id']}/qr-codes", headers=_auth_headers(token)
        )
        assert response.status_code == 200, response.text

    async def test_a_branch_scoped_read_holder_cannot_list_a_different_branchs_history(
        self,
        client: TestClient,
        owner: dict,
        restaurant_id: str,
        branch: dict,
        table: dict,
        session_factory,
    ) -> None:
        other_branch = client.post(
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=_auth_headers(owner["token"]),
            json={"name": "Uptown"},
        ).json()["data"]
        other_zone = client.post(
            f"/api/v1/branches/{other_branch['id']}/table-zones",
            headers=_auth_headers(owner["token"]),
            json={"name": "Bar"},
        ).json()["data"]
        other_table = client.post(
            f"/api/v1/branches/{other_branch['id']}/tables",
            headers=_auth_headers(owner["token"]),
            json={"tableZoneId": other_zone["id"], "tableNumber": "1", "capacity": 2},
        ).json()["data"]

        email = "scopedreader@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"table.read"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = client.get(
            f"/api/v1/tables/{other_table['id']}/qr-codes", headers=_auth_headers(token)
        )
        assert response.status_code == 403


class TestResolutionEndpointIsIsolatedFromManagement:
    """Step 4.7 adds ``GET /api/v1/qr/{token}`` -- this class only
    confirms it is physically isolated from the authenticated
    management routes tested above (no shared auth/permission gate, a
    different response envelope). The resolution endpoint's own
    behavior has its own dedicated test file, ``test_qr_resolution_router.py``.
    """

    def test_the_resolution_route_now_exists_and_is_unauthenticated(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/qr/some-token-value")
        # A public route: an unresolvable token is a clean 404, never a
        # 401 -- there is no authentication gate to fail here.
        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}

    def test_the_resolution_route_does_not_use_the_standard_api_envelope(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/qr/some-token-value")
        assert "data" not in response.json()
        assert "error" in response.json()

    def test_openapi_schema_now_has_the_resolution_path(self, client: TestClient) -> None:
        schema = client.get("/openapi.json").json()
        assert "/api/v1/qr/{token}" in schema["paths"]
        assert schema["paths"]["/api/v1/qr/{token}"]["get"].get("security") in (None, [])


class TestQRCodeConstraintsRemainIntact:
    async def test_token_uniqueness_is_still_enforced(
        self, client: TestClient, owner: dict, table: dict, session_factory
    ) -> None:
        code = _generate_qr_code(client, owner, table["id"])

        with pytest.raises(Exception):  # noqa: B017
            async with UnitOfWork(session_factory, TenantContext(owner["tenant_id"])) as uow:
                repo = SQLAlchemyQRCodeRepository(uow.session)
                await repo.create(
                    QRCode(
                        id=generate_ulid(),
                        tenant_id=owner["tenant_id"],
                        branch_id=table["branchId"],
                        table_id=table["id"],
                        token=code["token"],
                        status=QRCodeStatus.ACTIVE,
                        created_at=datetime.now(UTC),
                    )
                )

    async def test_status_check_constraint_is_still_enforced(
        self, session_factory, owner: dict, table: dict
    ) -> None:
        with pytest.raises(Exception):  # noqa: B017
            async with UnitOfWork(session_factory, TenantContext(owner["tenant_id"])) as uow:
                await uow.session.execute(
                    text(
                        "INSERT INTO qr_codes (id, tenant_id, branch_id, table_id, token, status) "
                        "VALUES (:id, :tenant_id, :branch_id, :table_id, :token, 'not_a_real_status')"
                    ),
                    {
                        "id": generate_ulid(),
                        "tenant_id": owner["tenant_id"],
                        "branch_id": table["branchId"],
                        "table_id": table["id"],
                        "token": generate_ulid(),
                    },
                )
