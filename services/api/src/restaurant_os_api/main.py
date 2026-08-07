"""FastAPI application factory.

Technical Architecture v2.0 SS5.13: registers middleware and routers.
Only the identity module's auth router exists so far — every future
module's presentation router is added here the same way.
"""

from __future__ import annotations

from fastapi import FastAPI

from restaurant_os_api.core.exceptions import register_exception_handlers
from restaurant_os_api.modules.identity.presentation.api.v1.auth_router import (
    router as auth_router,
)


def create_app() -> FastAPI:
    app = FastAPI(title="RestaurantOS API", version="0.1.0")

    register_exception_handlers(app)

    app.include_router(auth_router)

    @app.get("/health/live", include_in_schema=False)
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
