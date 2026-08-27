"""End-to-end HTTP tests for Operating Hours against a real PostgreSQL
instance (Sprint 5 Step 4.3).

Architecture SS7 defines exactly one endpoint -- ``PUT
/api/v1/branches/{id}/operating-hours``, a full-week replace, not
per-day CRUD -- and no dedicated GET; operating hours are read back
via the nested ``operatingHours`` array on ``GET /api/v1/branches/{id}``
(SS8's "Branch + Address + OperatingHours" Branch Details screen).
Follows test_branch_router.py's exact fixture/pattern conventions.
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
    """A user holding branch.read/branch.manage tenant-wide."""
    tenant_id = generate_ulid()
    email = "owner@example.com"
    user_id = await _seed_user(session_factory, tenant_id=tenant_id, email=email)
    await _grant_role(
        session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        permission_codes=frozenset({"branch.read", "branch.manage", "restaurant.read"}),
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
async def reader_only(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    email = "reader@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    await _grant_role(
        session_factory,
        tenant_id=owner["tenant_id"],
        user_id=user_id,
        permission_codes=frozenset({"branch.read"}),
    )
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


@pytest_asyncio.fixture
async def no_permission(session_factory, client: TestClient, owner: dict) -> AsyncGenerator[dict]:
    email = "noperm@example.com"
    user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
    token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
    yield {"tenant_id": owner["tenant_id"], "user_id": user_id, "token": token}


def _replace_body(**overrides) -> dict:
    body = {
        "entries": [
            {"dayOfWeek": 1, "isClosed": False, "opensAt": "09:00:00", "closesAt": "17:00:00"},
            {"dayOfWeek": 2, "isClosed": False, "opensAt": "09:00:00", "closesAt": "17:00:00"},
            {"dayOfWeek": 0, "isClosed": True},
        ]
    }
    body.update(overrides)
    return body


def _put_hours(client: TestClient, token: str, branch_id: str, body: dict):
    return client.put(
        f"/api/v1/branches/{branch_id}/operating-hours",
        headers=_auth_headers(token),
        json=body,
    )


class TestReplaceOperatingHours:
    def test_a_manage_holder_can_set_hours_and_they_are_returned_in_order(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = _put_hours(client, owner["token"], branch["id"], _replace_body())
        assert response.status_code == 200, response.text
        entries = response.json()["data"]
        assert [e["dayOfWeek"] for e in entries] == [0, 1, 2]
        assert entries[0]["isClosed"] is True
        assert entries[1]["opensAt"] == "09:00:00"

    def test_hours_are_visible_nested_in_get_branch(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        _put_hours(client, owner["token"], branch["id"], _replace_body())

        response = client.get(
            f"/api/v1/branches/{branch['id']}", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200, response.text
        entries = response.json()["data"]["operatingHours"]
        assert [e["dayOfWeek"] for e in entries] == [0, 1, 2]

    def test_a_branch_with_no_hours_configured_returns_an_empty_list(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = client.get(
            f"/api/v1/branches/{branch['id']}", headers=_auth_headers(owner["token"])
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["operatingHours"] == []

    def test_re_putting_fully_replaces_the_previous_week(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        _put_hours(client, owner["token"], branch["id"], _replace_body())

        second = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {"entries": [{"dayOfWeek": 5, "isClosed": True}]},
        )
        assert second.status_code == 200, second.text
        assert [e["dayOfWeek"] for e in second.json()["data"]] == [5]

        get_response = client.get(
            f"/api/v1/branches/{branch['id']}", headers=_auth_headers(owner["token"])
        )
        assert [e["dayOfWeek"] for e in get_response.json()["data"]["operatingHours"]] == [5]

    def test_putting_an_empty_list_clears_all_hours(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        _put_hours(client, owner["token"], branch["id"], _replace_body())

        response = _put_hours(client, owner["token"], branch["id"], {"entries": []})
        assert response.status_code == 200, response.text
        assert response.json()["data"] == []

    def test_split_shifts_multiple_open_periods_same_day_succeed(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {
                "entries": [
                    {
                        "dayOfWeek": 3,
                        "isClosed": False,
                        "opensAt": "11:00:00",
                        "closesAt": "14:00:00",
                    },
                    {
                        "dayOfWeek": 3,
                        "isClosed": False,
                        "opensAt": "17:00:00",
                        "closesAt": "22:00:00",
                    },
                ]
            },
        )
        assert response.status_code == 200, response.text
        assert len(response.json()["data"]) == 2

    def test_an_unknown_branch_is_404(self, client: TestClient, owner: dict) -> None:
        response = _put_hours(client, owner["token"], "0" * 26, _replace_body())
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    async def test_a_branch_in_another_tenant_is_404_not_a_leak(
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

        response = _put_hours(client, owner["token"], other_branch["id"], _replace_body())
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"

    def test_requires_authentication(self, client: TestClient, branch: dict) -> None:
        response = client.put(
            f"/api/v1/branches/{branch['id']}/operating-hours", json=_replace_body()
        )
        assert response.status_code == 401

    def test_denied_without_branch_manage(
        self, client: TestClient, reader_only: dict, branch: dict
    ) -> None:
        response = _put_hours(client, reader_only["token"], branch["id"], _replace_body())
        assert response.status_code == 403

    def test_denied_with_no_permission(
        self, client: TestClient, no_permission: dict, branch: dict
    ) -> None:
        response = _put_hours(client, no_permission["token"], branch["id"], _replace_body())
        assert response.status_code == 403

    async def test_denied_when_the_only_grant_is_on_an_inactive_role(
        self, client: TestClient, owner: dict, branch: dict, session_factory
    ) -> None:
        email = "inactive@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"branch.read", "branch.manage"}),
            is_active=False,
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = _put_hours(client, token, branch["id"], _replace_body())
        assert response.status_code == 403

    async def test_denied_once_the_grant_is_revoked(
        self, client: TestClient, owner: dict, branch: dict, session_factory
    ) -> None:
        email = "revoked@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        user_role_id = await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"branch.read", "branch.manage"}),
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)
        first = _put_hours(client, token, branch["id"], _replace_body())
        assert first.status_code == 200, first.text

        await _revoke_role(session_factory, tenant_id=owner["tenant_id"], user_role_id=user_role_id)

        second = _put_hours(client, token, branch["id"], _replace_body())
        assert second.status_code == 403

    async def test_a_branch_scoped_manage_grant_can_set_its_own_branch_hours(
        self, client: TestClient, owner: dict, branch: dict, session_factory
    ) -> None:
        email = "branchmgr@example.com"
        user_id = await _seed_user(session_factory, tenant_id=owner["tenant_id"], email=email)
        await _grant_role(
            session_factory,
            tenant_id=owner["tenant_id"],
            user_id=user_id,
            permission_codes=frozenset({"branch.read", "branch.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = _put_hours(client, token, branch["id"], _replace_body())
        assert response.status_code == 200, response.text

    async def test_a_branch_scoped_manage_grant_cannot_set_a_different_branchs_hours(
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
            permission_codes=frozenset({"branch.read", "branch.manage"}),
            branch_id=branch["id"],
        )
        token = _login_sync(client, tenant_id=owner["tenant_id"], email=email)

        response = _put_hours(client, token, other_branch["id"], _replace_body())
        assert response.status_code == 403

    def test_missing_required_field_on_an_entry_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = _put_hours(
            client, owner["token"], branch["id"], {"entries": [{"isClosed": False}]}
        )
        assert response.status_code == 422

    def test_a_day_of_week_out_of_range_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = _put_hours(
            client, owner["token"], branch["id"], {"entries": [{"dayOfWeek": 7, "isClosed": True}]}
        )
        assert response.status_code == 422

    def test_an_open_entry_missing_times_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {"entries": [{"dayOfWeek": 1, "isClosed": False}]},
        )
        assert response.status_code == 422

    def test_an_overnight_window_closing_after_midnight_is_accepted(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        # opens_at > closes_at used to be rejected outright. Every bar/pub
        # open past midnight needs exactly this shape -- closing on the
        # following calendar day, not an error.
        response = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {
                "entries": [
                    {
                        "dayOfWeek": 1,
                        "isClosed": False,
                        "opensAt": "12:30:00",
                        "closesAt": "00:30:00",
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        entry = response.json()["data"][0]
        assert entry["opensAt"] == "12:30:00"
        assert entry["closesAt"] == "00:30:00"

    def test_an_overnight_window_opening_in_the_evening_is_accepted(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {
                "entries": [
                    {
                        "dayOfWeek": 1,
                        "isClosed": False,
                        "opensAt": "18:00:00",
                        "closesAt": "02:00:00",
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        entry = response.json()["data"][0]
        assert entry["opensAt"] == "18:00:00"
        assert entry["closesAt"] == "02:00:00"

    def test_opens_at_equal_to_closes_at_is_rejected(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        # The one input that's still genuinely invalid for an open entry:
        # a zero-length window, regardless of the time of day chosen.
        response = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {
                "entries": [
                    {
                        "dayOfWeek": 1,
                        "isClosed": False,
                        "opensAt": "10:00:00",
                        "closesAt": "10:00:00",
                    }
                ]
            },
        )
        assert response.status_code == 422

    def test_multiple_invalid_days_surface_one_readable_message_per_day(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        # The original bug report: setting the same bad value on all 7
        # days used to dump 7 raw "body.entries.N: Value error, ..."
        # fragments into one string. Each day's message should now be a
        # standalone, day-labeled sentence instead.
        response = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {
                "entries": [
                    {
                        "dayOfWeek": day,
                        "isClosed": False,
                        "opensAt": "10:00:00",
                        "closesAt": "10:00:00",
                    }
                    for day in range(7)
                ]
            },
        )
        assert response.status_code == 422
        message = response.json()["error"]["message"]
        assert "entries." not in message
        assert "Value error" not in message
        for day_name in (
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ):
            assert f"{day_name}: opening and closing time cannot be the same" in message

    def test_a_closed_and_open_entry_for_the_same_day_is_a_conflict(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {
                "entries": [
                    {"dayOfWeek": 2, "isClosed": True},
                    {
                        "dayOfWeek": 2,
                        "isClosed": False,
                        "opensAt": "09:00:00",
                        "closesAt": "17:00:00",
                    },
                ]
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "OPERATING_HOURS_CONFLICT"

    def test_two_overlapping_open_periods_same_day_is_a_conflict(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {
                "entries": [
                    {
                        "dayOfWeek": 3,
                        "isClosed": False,
                        "opensAt": "09:00:00",
                        "closesAt": "15:00:00",
                    },
                    {
                        "dayOfWeek": 3,
                        "isClosed": False,
                        "opensAt": "14:00:00",
                        "closesAt": "22:00:00",
                    },
                ]
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "OPERATING_HOURS_CONFLICT"

    def test_duplicate_closed_entries_for_the_same_day_is_a_conflict(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        response = _put_hours(
            client,
            owner["token"],
            branch["id"],
            {"entries": [{"dayOfWeek": 4, "isClosed": True}, {"dayOfWeek": 4, "isClosed": True}]},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "OPERATING_HOURS_CONFLICT"


class TestReplaceOperatingHoursIdempotency:
    def test_the_same_key_and_body_replays_the_original_response(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/operating-hours"
        body = _replace_body()

        first = client.put(url, headers=headers, json=body)
        second = client.put(url, headers=headers, json=body)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()

    def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, client: TestClient, owner: dict, branch: dict
    ) -> None:
        key = generate_ulid()
        headers = {**_auth_headers(owner["token"]), "Idempotency-Key": key}
        url = f"/api/v1/branches/{branch['id']}/operating-hours"

        first = client.put(url, headers=headers, json=_replace_body())
        assert first.status_code == 200, first.text

        second = client.put(
            url, headers=headers, json={"entries": [{"dayOfWeek": 6, "isClosed": True}]}
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
