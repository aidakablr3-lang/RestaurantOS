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


class TestValidationErrorEnvelope:
    """Regression coverage for a pre-frontend release audit finding:
    without an explicit ``RequestValidationError`` handler, a `422`
    used FastAPI's own raw ``{"detail": [...]}`` body instead of the
    ``{success, error: {code, message}}`` envelope every other error
    in the API uses. See ``core/exceptions.py``'s own "Validation-error
    note" for the full reasoning."""

    def test_a_missing_required_field_uses_the_standard_envelope(self) -> None:
        client = TestClient(app)

        response = client.post("/api/v1/auth/login", json={})

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "tenantId" in body["error"]["message"]
        assert "email" in body["error"]["message"]
        assert "password" in body["error"]["message"]
        # The raw FastAPI shape must not leak through alongside it.
        assert "detail" not in body

    def test_an_out_of_range_field_uses_the_standard_envelope(self) -> None:
        client = TestClient(app)

        # An empty password fails `min_length=1` -- a real Field
        # constraint violation, not just a missing key.
        response = client.post(
            "/api/v1/auth/login",
            json={"tenantId": "0" * 26, "email": "a@b.com", "password": ""},
        )

        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "password" in body["error"]["message"]


class TestOpenApiSecurityScheme:
    """Regression coverage for the same audit's second finding: the
    OpenAPI schema declared no ``securitySchemes`` at all, so nothing
    machine-readable distinguished the one public route from the 69
    Bearer-token-gated ones. See ``main.py``'s own
    ``_UNAUTHENTICATED_OPERATIONS`` comment for the full reasoning."""

    def test_bearer_scheme_is_registered(self) -> None:
        schema = app.openapi()

        assert schema["components"]["securitySchemes"] == {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }

    def test_login_refresh_logout_and_qr_resolution_are_public(self) -> None:
        schema = app.openapi()

        assert schema["paths"]["/api/v1/auth/login"]["post"]["security"] == []
        assert schema["paths"]["/api/v1/auth/refresh"]["post"]["security"] == []
        assert schema["paths"]["/api/v1/auth/logout"]["post"]["security"] == []
        assert schema["paths"]["/api/v1/qr/{token}"]["get"]["security"] == []

    def test_every_other_operation_requires_the_bearer_scheme(self) -> None:
        schema = app.openapi()
        public = {
            ("/api/v1/auth/login", "post"),
            ("/api/v1/auth/refresh", "post"),
            ("/api/v1/auth/logout", "post"),
            ("/api/v1/qr/{token}", "get"),
            ("/api/v1/qr/{token}/menu", "get"),
            ("/api/v1/qr/{token}/orders", "post"),
            ("/api/v1/qr/{token}/orders/{order_id}/items", "post"),
            ("/api/v1/qr/{token}/orders/{order_id}/submit", "post"),
            ("/api/v1/qr/{token}/orders/{order_id}", "get"),
            ("/api/v1/owner-activation", "post"),
        }

        checked = 0
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                checked += 1
                if (path, method) in public:
                    assert operation["security"] == []
                else:
                    assert operation["security"] == [{"BearerAuth": []}], (
                        f"{method.upper()} {path} has unexpected security: "
                        f"{operation.get('security')!r}"
                    )
        # Sprint 7 Step 3 (Order + Kitchen) added 12 operations: 7 on
        # order_router, 2 on tab_router, 3 on kitchen_router.
        # Sprint 7 Step 4 (Billing + Payments + Ledger) added 11 more: 4 on
        # bill_router, 2 on discount_router, 3 on payment_router, 2 on
        # cash_drawer_router.
        # Sprint 7 Step 5 (Inventory + Recipe) added 10 more: 8 on
        # inventory_router, 2 on recipe_router.
        # Sprint 7 Step 6 (Purchasing) added 10 more: 3 on the supplier
        # routes, 7 on the purchase-order/receipt routes.
        # The full-day operational simulation's fix pass added 3 more:
        # GET /taxes, GET the open cash drawer, and POST an order item
        # void.
        # Guest QR ordering (guest-ordering gap fix) added 5 more, all
        # public: GET the menu, POST create order, POST add item, POST
        # submit, GET order status.
        # The End-of-Day report (full-day operational simulation gap fix)
        # added 1 more, authenticated: GET the report.
        # The payment/table-lifecycle P0 correction (2026-08-12) removed
        # 1: POST /payments/{id}/refund -- RestaurantOS v1 has no refund
        # workflow (see docs/AI_HANDOFF.md).
        # Gap 1 (user-creation API, 2026-08-16) added 2 more, authenticated:
        # POST and GET /api/v1/users -- found already missing from this
        # count when Phase 1 touched it; corrected here rather than left
        # silently stale.
        # Phase 1 (Setup Copilot, design doc SSA.4) added 1 more, public:
        # POST /api/v1/owner-activation.
        # Menu import from photo/PDF/CSV/XLSX added 2 more, both
        # authenticated (menu.manage): POST .../menu-imports/extract and
        # POST .../menu-imports/commit.
        assert checked == 129
