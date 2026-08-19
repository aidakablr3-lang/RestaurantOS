"""POST /api/v1/owner-activation — Phase 1 design doc SSA.4.

Unauthenticated, like ``auth_router.py``'s ``/login`` — no
``require_platform_admin``/``require_permission`` gate, because there is
no authenticated principal yet; the token itself is the credential.

**Identical failure response for unknown / expired / already-consumed
tokens, by construction, not by explicit branching here.**
``ActivateOwnerUseCase`` raises exactly one exception
(``InvalidOwnerActivationTokenError``) for all three conditions and
never exposes which one happened — the same "enumeration protection"
discipline ``qr_resolution_router.py``/``guest_order_router.py`` already
established for their own unauthenticated, token-is-the-credential
routes. That exception is left to propagate to the app's global domain-
exception handler (the same path ``InvalidCredentialsError`` takes from
``login`` — see ``auth_router.py``), so this router has no
``try``/``except`` for it at all: there is nothing here that could leak
a distinction the use case itself doesn't expose.

Rate limiting is the one thing this router does handle explicitly,
mirroring ``guest_order_router.py``'s own ``RateLimitExceededError`` ->
fixed ``429`` body pattern exactly.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.identity.application.dto import ActivateOwnerRequestDTO
from restaurant_os_api.modules.identity.presentation.dependencies import (
    ActivateOwnerUseCaseDep,
    OwnerActivationRateLimiterDep,
)
from restaurant_os_api.modules.identity.presentation.schemas.owner_activation_schemas import (
    ActivateOwnerRequestSchema,
)
from restaurant_os_api.platform.rate_limiting import RateLimitExceededError

router = APIRouter(tags=["owner-activation"])

_RATE_LIMITED_BODY = {"error": {"code": "RATE_LIMITED", "message": "Too many attempts."}}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


@router.post("/api/v1/owner-activation", response_model=ApiResponse[None])
async def activate_owner(
    body: ActivateOwnerRequestSchema,
    request: Request,
    use_case: ActivateOwnerUseCaseDep,
    rate_limiter: OwnerActivationRateLimiterDep,
) -> ApiResponse[None] | JSONResponse:
    try:
        await rate_limiter.check(source_ip=_client_ip(request), token=body.token)
    except RateLimitExceededError:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=_RATE_LIMITED_BODY
        )

    await use_case.execute(
        ActivateOwnerRequestDTO(token=body.token, new_password=body.new_password)
    )
    return ApiResponse(data=None)
