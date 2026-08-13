"""QR Code resolution endpoint (Sprint 5 Step 4.7).

Restaurant Platform Architecture SS7/SS11, ADR 0001 --
``GET /api/v1/qr/{token}``: the sole **unauthenticated** route in this
codebase. No ``AuthenticatedPrincipalDep``, no RBAC, no tenant context
-- deliberately, by architecture. Kept in its own router file and its
own dependency-wiring section (see ``dependencies.py``), physically
separate from ``qr_code_router.py``'s authenticated management routes
(``POST``/``GET /api/v1/tables/{id}/qr-codes``), which this file does
not import, reference, or alter in any way.

**Response contract (ADR 0001):** exactly ``{tenant_id, branch_id,
table_id}`` on success -- no ``ApiResponse`` envelope, no other field.
**Enumeration protection:** every non-resolvable outcome (token
missing, revoked, or rate-limited before the lookup) returns the exact
same generic 404 body, `{"error": "not_found"}` -- there is no
response-shape or status-code difference between "does not exist" and
"exists but revoked", per ADR 0001's own explicit requirement. A
rate-limit rejection returns 429 instead, which is standard, expected
throttling behavior and reveals nothing about any specific token's
existence.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Request, status
from fastapi.responses import JSONResponse

from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    ResolveQRCodeUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.qr_resolution_schemas import (
    QRResolutionResponseSchema,
)
from restaurant_os_api.platform.rate_limiting import RateLimitExceededError

router = APIRouter(tags=["qr-resolution"])

TokenPath = Annotated[str, Path()]

_NOT_FOUND_BODY = {"error": "not_found"}
_RATE_LIMITED_BODY = {"error": "rate_limited"}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


@router.get("/api/v1/qr/{token}", response_model=QRResolutionResponseSchema)
async def resolve_qr_code(
    token: TokenPath,
    request: Request,
    use_case: ResolveQRCodeUseCaseDep,
) -> JSONResponse:
    try:
        result = await use_case.execute(token, _client_ip(request))
    except RateLimitExceededError:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=_RATE_LIMITED_BODY
        )

    if result is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=_NOT_FOUND_BODY)

    body = QRResolutionResponseSchema(
        tenant_id=result.tenant_id, branch_id=result.branch_id, table_id=result.table_id
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=body.model_dump())
