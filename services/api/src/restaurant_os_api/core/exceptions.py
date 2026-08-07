"""Global exception -> HTTP status mapping.

Technical Architecture v2.0 SS5.4: a single global handler maps the
known domain exception hierarchy to HTTP responses; anything unexpected
maps to 500 with a generic message, is logged with full context, and
never leaks internals (a stack trace, an ORM error string) to the
caller.

Status-code note: TENANT_NOT_ACTIVE and USER_NOT_ACTIVE map to 401
(not 403) deliberately — returning a different status for "exists but
suspended/deactivated" versus "invalid credentials" would let an
attacker enumerate valid tenant/account identifiers by status code alone.
This mirrors InvalidCredentialsError's own documented rationale. Fully
timing-safe enumeration resistance across every one of these paths is
tracked as a follow-up hardening item, not claimed as complete here.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiErrorDetail, ApiErrorResponse
from restaurant_os_api.modules.identity.domain.exceptions import IdentityDomainError

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR_CODE: dict[str, int] = {
    "TENANT_NOT_FOUND": status.HTTP_401_UNAUTHORIZED,
    "TENANT_NOT_ACTIVE": status.HTTP_401_UNAUTHORIZED,
    "USER_NOT_FOUND": status.HTTP_401_UNAUTHORIZED,
    "USER_NOT_ACTIVE": status.HTTP_401_UNAUTHORIZED,
    "INVALID_CREDENTIALS": status.HTTP_401_UNAUTHORIZED,
    "INVALID_REFRESH_TOKEN": status.HTTP_401_UNAUTHORIZED,
    "SESSION_REVOKED": status.HTTP_401_UNAUTHORIZED,
    "INVALID_EMAIL_ADDRESS": status.HTTP_400_BAD_REQUEST,
    # Sprint 4.1 (Tenant Platform) additions:
    "INVALID_ACCESS_TOKEN": status.HTTP_401_UNAUTHORIZED,
    "INSUFFICIENT_PRIVILEGES": status.HTTP_403_FORBIDDEN,
    "INVALID_TENANT_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "TENANT_LEGAL_NAME_CONFLICT": status.HTTP_409_CONFLICT,
    "SUBSCRIPTION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
}

_DEFAULT_STATUS = status.HTTP_422_UNPROCESSABLE_ENTITY


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IdentityDomainError)
    async def handle_identity_domain_error(
        request: Request, exc: IdentityDomainError
    ) -> JSONResponse:
        http_status = _STATUS_BY_ERROR_CODE.get(exc.error_code, _DEFAULT_STATUS)
        envelope = ApiErrorResponse(error=ApiErrorDetail(code=exc.error_code, message=exc.message))
        return JSONResponse(
            status_code=http_status,
            content=envelope.model_dump(by_alias=True),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception processing %s %s", request.method, request.url)
        envelope = ApiErrorResponse(
            error=ApiErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred. Please try again.",
            )
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=envelope.model_dump(by_alias=True),
        )
