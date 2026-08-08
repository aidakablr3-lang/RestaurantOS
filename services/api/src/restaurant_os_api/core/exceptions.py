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
from typing import Any, Protocol

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiErrorDetail, ApiErrorResponse
from restaurant_os_api.modules.identity.domain.exceptions import IdentityDomainError
from restaurant_os_api.modules.restaurant.domain.exceptions import RestaurantDomainError
from restaurant_os_api.platform.idempotency.exceptions import IdempotencyError


class _DomainErrorLike(Protocol):
    """The shape every module's domain-exception base class already
    shares (``IdentityDomainError``, ``RestaurantDomainError``,
    ``IdempotencyError``) without a common base class between them --
    each module owns its own hierarchy by design (Technical
    Architecture v2.0's module-boundary rule), so this Protocol, not
    inheritance, is what lets ``build_error_response`` accept any of
    them."""

    error_code: str
    message: str


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
    # RBAC Foundation (Sprint 5, Step 2) additions:
    "ROLE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "PERMISSION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "USER_ROLE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "ROLE_NAME_CONFLICT": status.HTTP_409_CONFLICT,
    "DUPLICATE_ROLE_ASSIGNMENT": status.HTTP_409_CONFLICT,
    "INVALID_ROLE_LIFECYCLE_TRANSITION": status.HTTP_409_CONFLICT,
    "INVALID_PERMISSION_STATE_TRANSITION": status.HTTP_409_CONFLICT,
    "ROLE_NOT_ACTIVE": status.HTTP_409_CONFLICT,
    "INSUFFICIENT_GRANT_AUTHORITY": status.HTTP_403_FORBIDDEN,
    "PERMISSION_DENIED": status.HTTP_403_FORBIDDEN,
    # Restaurant Platform (Sprint 5, Step 4) additions:
    "INVALID_RESTAURANT_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "INVALID_BRANCH_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "INVALID_QR_CODE_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "INVALID_RESERVATION_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "BRANCH_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    # Shared idempotency infrastructure (Sprint 5, Step 4.0) additions:
    "IDEMPOTENCY_KEY_CONFLICT": status.HTTP_409_CONFLICT,
    "IDEMPOTENT_REQUEST_IN_PROGRESS": status.HTTP_409_CONFLICT,
}

_DEFAULT_STATUS = status.HTTP_422_UNPROCESSABLE_ENTITY


def build_error_response(exc: _DomainErrorLike) -> tuple[int, dict[str, Any]]:
    """Shapes a known domain exception into ``(http_status,
    response_body)`` -- the exact pair ``IdempotencyGuard.run()``'s
    ``execute`` callable needs to cache and replay an expected 4xx the
    same way it caches a 2xx (see ``platform/idempotency/guard.py``).
    The single source of truth both this module's own exception
    handler and idempotent use-case wrapping share, so the two never
    drift apart."""
    http_status = _STATUS_BY_ERROR_CODE.get(exc.error_code, _DEFAULT_STATUS)
    envelope = ApiErrorResponse(error=ApiErrorDetail(code=exc.error_code, message=exc.message))
    return http_status, envelope.model_dump(by_alias=True)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IdentityDomainError)
    async def handle_identity_domain_error(
        request: Request, exc: IdentityDomainError
    ) -> JSONResponse:
        http_status, body = build_error_response(exc)
        return JSONResponse(status_code=http_status, content=body)

    @app.exception_handler(RestaurantDomainError)
    async def handle_restaurant_domain_error(
        request: Request, exc: RestaurantDomainError
    ) -> JSONResponse:
        http_status, body = build_error_response(exc)
        return JSONResponse(status_code=http_status, content=body)

    @app.exception_handler(IdempotencyError)
    async def handle_idempotency_error(request: Request, exc: IdempotencyError) -> JSONResponse:
        http_status, body = build_error_response(exc)
        return JSONResponse(status_code=http_status, content=body)

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
