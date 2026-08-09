"""FastAPI application factory.

Technical Architecture v2.0 SS5.13: registers middleware and routers.
Every module's presentation router is added here the same way.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from restaurant_os_api.modules.restaurant.presentation.api.v1.branch_router import (
    router as branch_router,
)
from restaurant_os_api.modules.restaurant.presentation.api.v1.qr_code_router import (
    router as qr_code_router,
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


def create_app() -> FastAPI:
    app = FastAPI(title="RestaurantOS API", version="0.1.0")

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

    @app.get("/health/live", include_in_schema=False)
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
