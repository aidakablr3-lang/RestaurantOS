"""End-to-end HTTP + rate-limiter integration tests for the public QR
Code resolution endpoint against a real PostgreSQL instance (Sprint 5
Step 4.7, ADR 0001).

Scoped to ``GET /api/v1/qr/{token}`` only -- the authenticated
management routes (``POST``/``GET /api/v1/tables/{id}/qr-codes``) have
their own dedicated file, ``test_qr_code_router.py``, and this file
never imports or exercises them. Seeding here goes straight through the
restaurant module's repositories (not the authenticated API) since this
endpoint must work with zero dependency on any authenticated flow.

Rate-limit assertions import the limiter's own module-private
threshold constants rather than hardcoding duplicate numbers that could
silently drift out of sync with ``platform/rate_limiting/limiter.py``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from restaurant_os_api.core.ids import generate_qr_token, generate_ulid
from restaurant_os_api.main import create_app
from restaurant_os_api.modules.identity.presentation.dependencies import get_session_factory
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    QRCode,
    QRCodeStatus,
    Restaurant,
    RestaurantStatus,
    Table,
    TableStatus,
    TableZone,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyBranchRepository,
    SQLAlchemyQRCodeRepository,
    SQLAlchemyRestaurantRepository,
    SQLAlchemyTableRepository,
    SQLAlchemyTableZoneRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.rate_limiting import RateLimitExceededError
from restaurant_os_api.platform.rate_limiting.limiter import (
    _IP_FAILED_LIMIT,
    _IP_TOTAL_LIMIT,
    _TOKEN_FAILED_LIMIT,
    _TOKEN_TOTAL_LIMIT,
    QRResolutionRateLimiter,
    _window_start,
)
from restaurant_os_api.platform.tenancy import TenantContext

RESOLUTION_PATH = "/api/v1/qr/{token}"


def _client(session_factory, *, ip: str = "203.0.113.10") -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    return TestClient(app, client=(ip, 12345))


async def _seed_tenant(session_factory, tenant_id: str) -> None:
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO tenants (id, legal_name, display_name, tenant_tier, status, "
                "default_currency_code) VALUES (:id, :name, :name, 'shared', 'active', 'USD') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tenant_id, "name": f"Seed tenant {tenant_id}"},
        )


async def _seed_table(session_factory, tenant_id: str) -> dict[str, str]:
    """Seeds restaurant -> branch -> table_zone -> table via the real
    repositories, returning every id a resolution test needs."""
    await _seed_tenant(session_factory, tenant_id)
    now = datetime.now(UTC)
    restaurant_id = generate_ulid()
    branch_id = generate_ulid()
    table_zone_id = generate_ulid()
    table_id = generate_ulid()
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await SQLAlchemyRestaurantRepository(uow.session).create(
            Restaurant(
                id=restaurant_id,
                tenant_id=tenant_id,
                legal_name="R",
                display_name="R",
                default_currency_code="USD",
                status=RestaurantStatus.ACTIVE,
                created_at=now,
            )
        )
        await SQLAlchemyBranchRepository(uow.session).create(
            Branch(
                id=branch_id,
                tenant_id=tenant_id,
                restaurant_id=restaurant_id,
                name="Downtown",
                status=BranchStatus.ACTIVE,
                created_at=now,
            )
        )
        await SQLAlchemyTableZoneRepository(uow.session).create(
            TableZone(
                id=table_zone_id,
                tenant_id=tenant_id,
                branch_id=branch_id,
                name="Patio",
                display_order=1,
                created_at=now,
            )
        )
        await SQLAlchemyTableRepository(uow.session).create(
            Table(
                id=table_id,
                tenant_id=tenant_id,
                branch_id=branch_id,
                table_zone_id=table_zone_id,
                table_number="1",
                capacity=4,
                status=TableStatus.AVAILABLE,
                sync_version=1,
                created_at=now,
            )
        )
    return {
        "tenant_id": tenant_id,
        "restaurant_id": restaurant_id,
        "branch_id": branch_id,
        "table_zone_id": table_zone_id,
        "table_id": table_id,
    }


async def _seed_qr_code(
    session_factory, table: dict[str, str], *, status: QRCodeStatus = QRCodeStatus.ACTIVE
) -> QRCode:
    async with UnitOfWork(session_factory, TenantContext(table["tenant_id"])) as uow:
        return await SQLAlchemyQRCodeRepository(uow.session).create(
            QRCode(
                id=generate_ulid(),
                tenant_id=table["tenant_id"],
                branch_id=table["branch_id"],
                table_id=table["table_id"],
                token=generate_qr_token(),
                status=status,
                created_at=datetime.now(UTC),
            )
        )


async def _seed_counter(
    session_factory,
    *,
    bucket_type: str,
    bucket_key: str,
    total_count: int = 0,
    failed_count: int = 0,
) -> None:
    """Pre-seeds a rate-limit counter row for the *current* fixed window.

    Used instead of driving a real N-request loop to exhaust a limit:
    the window is real wall-clock time, and a loop of dozens of real
    HTTP/DB round trips is slow enough to risk crossing a window
    boundary mid-test, silently resetting the counter and making the
    assertion flaky. Seeding the boundary value directly and then
    issuing exactly one real request keeps the whole test inside a
    single window regardless of when in the minute it happens to run.
    """
    window_start = _window_start(datetime.now(UTC))
    async with UnitOfWork(session_factory) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO qr_resolution_rate_limits "
                "(id, bucket_type, bucket_key, window_start, total_count, failed_count) "
                "VALUES (:id, :bucket_type, :bucket_key, :window_start, :total_count, :failed_count)"
            ),
            {
                "id": generate_ulid(),
                "bucket_type": bucket_type,
                "bucket_key": bucket_key,
                "window_start": window_start,
                "total_count": total_count,
                "failed_count": failed_count,
            },
        )


class TestResolution:
    async def test_an_active_token_resolves_to_exactly_the_three_ids(self, session_factory) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        qr = await _seed_qr_code(session_factory, table)

        response = _client(session_factory).get(RESOLUTION_PATH.format(token=qr.token))

        assert response.status_code == 200
        assert response.json() == {
            "tenant_id": table["tenant_id"],
            "branch_id": table["branch_id"],
            "table_id": table["table_id"],
        }

    async def test_the_response_has_no_extra_fields(self, session_factory) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        qr = await _seed_qr_code(session_factory, table)

        response = _client(session_factory).get(RESOLUTION_PATH.format(token=qr.token))

        assert set(response.json().keys()) == {"tenant_id", "branch_id", "table_id"}

    async def test_a_revoked_token_does_not_resolve(self, session_factory) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        qr = await _seed_qr_code(session_factory, table, status=QRCodeStatus.REVOKED)

        response = _client(session_factory).get(RESOLUTION_PATH.format(token=qr.token))

        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}

    async def test_a_nonexistent_token_does_not_resolve(self, session_factory) -> None:
        response = _client(session_factory).get(
            RESOLUTION_PATH.format(token="totally-nonexistent-token")
        )

        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}

    async def test_no_authentication_is_required(self, session_factory) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        qr = await _seed_qr_code(session_factory, table)

        # Deliberately no Authorization header at all.
        response = _client(session_factory).get(RESOLUTION_PATH.format(token=qr.token))

        assert response.status_code == 200

    async def test_an_invalid_authorization_header_is_ignored_not_rejected(
        self, session_factory
    ) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        qr = await _seed_qr_code(session_factory, table)

        response = _client(session_factory).get(
            RESOLUTION_PATH.format(token=qr.token),
            headers={"Authorization": "Bearer not-a-real-jwt-at-all"},
        )

        assert response.status_code == 200


class TestEnumerationProtection:
    async def test_nonexistent_and_revoked_produce_identical_status_and_body(
        self, session_factory
    ) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        revoked = await _seed_qr_code(session_factory, table, status=QRCodeStatus.REVOKED)
        client = _client(session_factory)

        missing_response = client.get(RESOLUTION_PATH.format(token="totally-nonexistent-token"))
        revoked_response = client.get(RESOLUTION_PATH.format(token=revoked.token))

        assert missing_response.status_code == revoked_response.status_code == 404
        assert missing_response.json() == revoked_response.json() == {"error": "not_found"}
        assert missing_response.headers["content-type"] == revoked_response.headers["content-type"]

    async def test_revoked_tokens_never_leak_table_information(self, session_factory) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        revoked = await _seed_qr_code(session_factory, table, status=QRCodeStatus.REVOKED)

        response = _client(session_factory).get(RESOLUTION_PATH.format(token=revoked.token))

        body_text = response.text
        assert table["tenant_id"] not in body_text
        assert table["branch_id"] not in body_text
        assert table["table_id"] not in body_text


class TestRateLimitBucketIsolation:
    async def test_exhausting_one_ips_total_limit_does_not_affect_a_different_ip(
        self, session_factory
    ) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        ip_a, ip_b = "198.51.100.11", "198.51.100.22"
        await _seed_counter(
            session_factory, bucket_type="ip", bucket_key=ip_a, total_count=_IP_TOTAL_LIMIT
        )

        qr = await _seed_qr_code(session_factory, table)
        response = _client(session_factory, ip=ip_a).get(RESOLUTION_PATH.format(token=qr.token))
        assert response.status_code == 429
        assert response.json() == {"error": "rate_limited"}

        # IP B has made zero requests -- its bucket is untouched.
        response = _client(session_factory, ip=ip_b).get(RESOLUTION_PATH.format(token=qr.token))
        assert response.status_code == 200

    async def test_exhausting_one_tokens_total_limit_does_not_affect_a_different_token(
        self, session_factory
    ) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        qr_a = await _seed_qr_code(session_factory, table)
        qr_b = await _seed_qr_code(session_factory, table)
        await _seed_counter(
            session_factory,
            bucket_type="token",
            bucket_key=qr_a.token,
            total_count=_TOKEN_TOTAL_LIMIT,
        )

        blocked_client = _client(session_factory, ip="198.51.100.200")
        response = blocked_client.get(RESOLUTION_PATH.format(token=qr_a.token))
        assert response.status_code == 429

        # Token B has never been requested -- its bucket is untouched.
        response = blocked_client.get(RESOLUTION_PATH.format(token=qr_b.token))
        assert response.status_code == 200


class TestFailedResolutionStricterLimit:
    async def test_repeated_failures_from_one_ip_trip_the_failed_limit_before_the_total_limit(
        self, session_factory
    ) -> None:
        assert _IP_FAILED_LIMIT < _IP_TOTAL_LIMIT
        client = _client(session_factory, ip="198.51.100.77")

        responses = [
            client.get(RESOLUTION_PATH.format(token=f"nonexistent-{i}"))
            for i in range(_IP_FAILED_LIMIT + 1)
        ]

        not_found = [r for r in responses if r.status_code == 404]
        rate_limited = [r for r in responses if r.status_code == 429]
        assert len(not_found) == _IP_FAILED_LIMIT
        assert len(rate_limited) == 1
        assert rate_limited[0].json() == {"error": "rate_limited"}

    async def test_repeated_failures_against_one_token_trip_the_per_token_failed_limit(
        self, session_factory
    ) -> None:
        assert _TOKEN_FAILED_LIMIT < _IP_FAILED_LIMIT
        same_nonexistent_token = "same-nonexistent-token-reused"

        # A distinct IP per request keeps the per-IP failed limit from
        # tripping first and confounding this token-only assertion.
        responses = []
        for i in range(_TOKEN_FAILED_LIMIT + 1):
            client = _client(session_factory, ip=f"198.51.100.{150 + i}")
            responses.append(client.get(RESOLUTION_PATH.format(token=same_nonexistent_token)))

        not_found = [r for r in responses if r.status_code == 404]
        rate_limited = [r for r in responses if r.status_code == 429]
        assert len(not_found) == _TOKEN_FAILED_LIMIT
        assert len(rate_limited) == 1


class TestSuccessfulResolutionIsNotThrottledByFailureLimits:
    async def test_repeated_successful_resolutions_are_unaffected_by_the_failed_limit(
        self, session_factory
    ) -> None:
        # More successful resolutions than either failed-limit constant,
        # from a single IP+token pair -- since successes never touch
        # failed_count, none of these should be rate-limited.
        attempts = max(_IP_FAILED_LIMIT, _TOKEN_FAILED_LIMIT) + 3
        table = await _seed_table(session_factory, generate_ulid())
        qr = await _seed_qr_code(session_factory, table)
        client = _client(session_factory, ip="198.51.100.180")

        responses = [client.get(RESOLUTION_PATH.format(token=qr.token)) for _ in range(attempts)]

        assert all(r.status_code == 200 for r in responses)


class TestRateLimiterWindowBehavior:
    async def test_a_stale_windows_exhausted_count_does_not_block_the_current_window(
        self, session_factory
    ) -> None:
        limiter = QRResolutionRateLimiter(session_factory)
        ip = "198.51.100.199"
        stale_window_start = _window_start(datetime.now(UTC)) - timedelta(seconds=120)

        async with UnitOfWork(session_factory) as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO qr_resolution_rate_limits "
                    "(id, bucket_type, bucket_key, window_start, total_count, failed_count) "
                    "VALUES (:id, 'ip', :ip, :window_start, :count, 0)"
                ),
                {
                    "id": generate_ulid(),
                    "ip": ip,
                    "window_start": stale_window_start,
                    "count": _IP_TOTAL_LIMIT + 100,
                },
            )

        # The stale row belongs to a window well in the past; the current
        # window's counter for this IP starts fresh at zero.
        await limiter.check(source_ip=ip, token=generate_qr_token())


class TestRateLimiterConcurrency:
    async def test_concurrent_checks_for_the_same_ip_bucket_cannot_exceed_the_limit(
        self, session_factory
    ) -> None:
        limiter = QRResolutionRateLimiter(session_factory)
        ip = "198.51.100.201"
        attempts = _IP_TOTAL_LIMIT + 20

        results = await asyncio.gather(
            *(limiter.check(source_ip=ip, token=f"concurrent-token-{i}") for i in range(attempts)),
            return_exceptions=True,
        )

        successes = [r for r in results if r is None]
        failures = [r for r in results if isinstance(r, RateLimitExceededError)]
        unexpected = [
            r for r in results if r is not None and not isinstance(r, RateLimitExceededError)
        ]
        assert unexpected == []
        assert len(successes) == _IP_TOTAL_LIMIT
        assert len(failures) == attempts - _IP_TOTAL_LIMIT


class TestMalformedTokenSafety:
    async def test_a_very_long_token_does_not_cause_a_server_error(self, session_factory) -> None:
        response = _client(session_factory, ip="198.51.100.90").get(
            RESOLUTION_PATH.format(token="x" * 10_000)
        )

        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}

    async def test_a_token_shaped_like_a_sql_injection_attempt_is_handled_safely(
        self, session_factory
    ) -> None:
        response = _client(session_factory, ip="198.51.100.91").get("/api/v1/qr/" + "' OR '1'='1")

        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}

    async def test_a_random_high_entropy_token_does_not_resolve(self, session_factory) -> None:
        response = _client(session_factory, ip="198.51.100.92").get(
            RESOLUTION_PATH.format(token=generate_qr_token())
        )

        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}


class TestNoAuthenticationOrRBACIsConsulted:
    async def test_tenant_id_in_the_response_cannot_be_influenced_by_query_parameters(
        self, session_factory
    ) -> None:
        table = await _seed_table(session_factory, generate_ulid())
        qr = await _seed_qr_code(session_factory, table)
        other_tenant_id = generate_ulid()

        response = _client(session_factory, ip="198.51.100.93").get(
            RESOLUTION_PATH.format(token=qr.token), params={"tenant_id": other_tenant_id}
        )

        assert response.status_code == 200
        assert response.json()["tenant_id"] == table["tenant_id"]

    async def test_two_tenants_tokens_each_resolve_to_only_their_own_ids(
        self, session_factory
    ) -> None:
        table_a = await _seed_table(session_factory, generate_ulid())
        table_b = await _seed_table(session_factory, generate_ulid())
        qr_a = await _seed_qr_code(session_factory, table_a)
        qr_b = await _seed_qr_code(session_factory, table_b)
        client = _client(session_factory, ip="198.51.100.94")

        response_a = client.get(RESOLUTION_PATH.format(token=qr_a.token))
        response_b = client.get(RESOLUTION_PATH.format(token=qr_b.token))

        assert response_a.json()["tenant_id"] == table_a["tenant_id"]
        assert response_b.json()["tenant_id"] == table_b["tenant_id"]
        assert response_a.json()["tenant_id"] != response_b.json()["tenant_id"]


class TestOpenAPIRegistration:
    async def test_the_resolution_route_is_registered_and_requires_no_security(
        self, session_factory
    ) -> None:
        schema = _client(session_factory).get("/openapi.json").json()

        path_item = schema["paths"]["/api/v1/qr/{token}"]
        get_operation = path_item["get"]
        assert get_operation.get("security") in (None, [])
