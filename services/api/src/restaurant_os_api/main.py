"""FastAPI application factory.

Technical Architecture v2.0 SS5.13: registers middleware and routers.
Every module's presentation router is added here the same way.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from restaurant_os_api.core.config import get_settings
from restaurant_os_api.core.exceptions import register_exception_handlers
from restaurant_os_api.modules.identity.presentation.api.v1.admin_tenant_router import (
    router as admin_tenant_router,
)
from restaurant_os_api.modules.identity.presentation.api.v1.auth_router import (
    router as auth_router,
)
from restaurant_os_api.modules.identity.presentation.api.v1.rbac_router import (
    router as rbac_router,
)
from restaurant_os_api.modules.identity.presentation.api.v1.self_service_tenant_router import (
    router as self_service_tenant_router,
)
from restaurant_os_api.modules.operations.presentation.api.v1.bill_router import (
    router as bill_router,
)
from restaurant_os_api.modules.operations.presentation.api.v1.cash_drawer_router import (
    router as cash_drawer_router,
)
from restaurant_os_api.modules.operations.presentation.api.v1.discount_router import (
    router as discount_router,
)
from restaurant_os_api.modules.operations.presentation.api.v1.inventory_router import (
    router as inventory_router,
)
from restaurant_os_api.modules.operations.presentation.api.v1.kitchen_router import (
    router as kitchen_router,
)
from restaurant_os_api.modules.operations.presentation.api.v1.order_router import (
    router as order_router,
)
from restaurant_os_api.modules.operations.presentation.api.v1.payment_router import (
    router as payment_router,
)
from restaurant_os_api.modules.operations.presentation.api.v1.recipe_router import (
    router as recipe_router,
)
from restaurant_os_api.modules.operations.presentation.api.v1.tab_router import (
    router as tab_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.branch_router import (
    router as branch_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.menu_category_router import (
    router as menu_category_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.menu_item_router import (
    router as menu_item_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.modifier_group_router import (
    router as modifier_group_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.modifier_router import (
    router as modifier_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.qr_code_router import (
    router as qr_code_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.qr_resolution_router import (
    router as qr_resolution_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.reservation_router import (
    router as reservation_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.restaurant_router import (
    router as restaurant_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.table_router import (
    router as table_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.table_zone_router import (
    router as table_zone_router,
)

# Every route in this API is Bearer-token-gated except these four --
# the three auth routes (which hand out or invalidate the token itself,
# so requiring one to call them would be circular) and the one
# deliberately unauthenticated QR guest-resolution route (ADR 0001).
# Auth is a raw ``Authorization`` header dependency (``require_authenticated_user``),
# not ``fastapi.security``'s ``HTTPBearer``, so FastAPI never auto-populates
# ``security`` in the OpenAPI schema on its own -- without this, the schema
# didn't document which routes need a token at all (found in a pre-frontend
# release audit). This only edits the generated schema, never runtime
# request handling, so it carries zero behavior-change risk.
_UNAUTHENTICATED_OPERATIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/refresh", "post"),
        ("/api/v1/auth/logout", "post"),
        ("/api/v1/qr/{token}", "get"),
    }
)


def create_app() -> FastAPI:
    app = FastAPI(title="RestaurantOS API", version="0.1.0")

    def custom_openapi() -> dict[str, object]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
        for path, operations in schema.get("paths", {}).items():
            for method, operation in operations.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                is_public = (path, method) in _UNAUTHENTICATED_OPERATIONS
                operation["security"] = [] if is_public else [{"BearerAuth": []}]
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    # Every client (admin-web, customer-ordering, kitchen-display) is a
    # browser app calling this API cross-origin. Auth is Bearer-token-based
    # (Authorization header, never a cookie), so allow_credentials stays
    # False -- no session cookie crosses origins, so there is nothing for
    # credentialed CORS to protect here.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(auth_router)
    app.include_router(admin_tenant_router)
    app.include_router(self_service_tenant_router)
    app.include_router(rbac_router)
    app.include_router(restaurant_router)
    app.include_router(branch_router)
    app.include_router(table_zone_router)
    app.include_router(table_router)
    app.include_router(qr_code_router)
    app.include_router(qr_resolution_router)
    app.include_router(menu_category_router)
    app.include_router(menu_item_router)
    app.include_router(modifier_group_router)
    app.include_router(modifier_router)
    app.include_router(reservation_router)
    app.include_router(order_router)
    app.include_router(tab_router)
    app.include_router(kitchen_router)
    app.include_router(bill_router)
    app.include_router(discount_router)
    app.include_router(payment_router)
    app.include_router(cash_drawer_router)
    app.include_router(inventory_router)
    app.include_router(recipe_router)

    @app.get("/health/live", include_in_schema=False)
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
