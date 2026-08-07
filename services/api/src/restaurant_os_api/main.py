"""FastAPI application factory.

Technical Architecture v2.0 SS5.13: registers middleware and routers.
Every module's presentation router is added here the same way.
"""

from __future__ import annotations

from fastapi import FastAPI

from restaurant_os_api.core.exceptions import register_exception_handlers
from restaurant_os_api.modules.identity.presentation.api.v1.admin_tenant_router import (
    router as admin_tenant_router,
)
from restaurant_os_api.modules.identity.presentation.api.v1.auth_router import (
    router as auth_router,
)
from restaurant_os_api.modules.identity.presentation.api.v1.self_service_tenant_router import (
    router as self_service_tenant_router,
)


def create_app() -> FastAPI:
    app = FastAPI(title="RestaurantOS API", version="0.1.0")

    register_exception_handlers(app)

    app.include_router(auth_router)
    app.include_router(admin_tenant_router)
    app.include_router(self_service_tenant_router)

    @app.get("/health/live", include_in_schema=False)
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
