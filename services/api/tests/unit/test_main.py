"""Unit test for the app factory's CORS wiring.

Regression coverage for a defect found during Sprint 4.1 Step 3 browser
verification: the app had no CORS middleware, so every browser client's
preflight `OPTIONS` request was rejected before reaching any route --
confirmed independently with a minimal asyncpg-free reproduction (a
plain `OPTIONS` request against a real running instance returned 405
with no `Access-Control-Allow-Origin` header). This test exercises the
same preflight path via FastAPI's TestClient, which needs no database
-- CORSMiddleware runs before routing.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from restaurant_os_api.main import app


def test_preflight_from_an_allowed_origin_gets_cors_headers() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_preflight_from_a_disallowed_origin_gets_no_cors_headers() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert "access-control-allow-origin" not in response.headers
