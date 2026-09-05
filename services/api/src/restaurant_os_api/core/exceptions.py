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

Validation-error note: without an explicit ``RequestValidationError``
handler here, FastAPI's own built-in one wins (it's registered before
``create_app()`` ever runs) and returns its raw ``{"detail": [...]}``
body -- the one response shape in this entire API that didn't match
the shared ``{success, data|error}`` envelope every other route uses.
Found during a pre-frontend release audit; closed below so a frontend
client never needs a second error-parsing path for one status code.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiErrorDetail, ApiErrorResponse
from restaurant_os_api.modules.identity.domain.exceptions import IdentityDomainError
from restaurant_os_api.modules.operations.domain.exceptions import OperationsDomainError
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
    "INVALID_OWNER_ACTIVATION_TOKEN": status.HTTP_401_UNAUTHORIZED,
    "INVALID_EMAIL_ADDRESS": status.HTTP_400_BAD_REQUEST,
    # Sprint 4.1 (Tenant Platform) additions:
    "INVALID_ACCESS_TOKEN": status.HTTP_401_UNAUTHORIZED,
    "INSUFFICIENT_PRIVILEGES": status.HTTP_403_FORBIDDEN,
    "INVALID_TENANT_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "TENANT_LEGAL_NAME_CONFLICT": status.HTTP_409_CONFLICT,
    "USER_EMAIL_CONFLICT": status.HTTP_409_CONFLICT,
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
    "RESTAURANT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "BRANCH_NAME_CONFLICT": status.HTTP_409_CONFLICT,
    "INVOICE_PREFIX_CONFLICT": status.HTTP_409_CONFLICT,
    "OPERATING_HOURS_CONFLICT": status.HTTP_409_CONFLICT,
    "TABLE_ZONE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "TABLE_ZONE_NAME_CONFLICT": status.HTTP_409_CONFLICT,
    "TABLE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "TABLE_NUMBER_ALREADY_EXISTS": status.HTTP_409_CONFLICT,
    # Menu Catalogue (Sprint 5, Step 4.8) additions:
    "MENU_CATEGORY_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "MENU_CATEGORY_NAME_CONFLICT": status.HTTP_409_CONFLICT,
    "MENU_ITEM_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "MODIFIER_GROUP_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "MODIFIER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    # Menu import from photo/PDF/CSV/XLSX additions:
    "MENU_IMPORT_NOT_CONFIGURED": status.HTTP_503_SERVICE_UNAVAILABLE,
    "MENU_IMPORT_UNSUPPORTED_FILE": status.HTTP_400_BAD_REQUEST,
    "MENU_IMPORT_EXTRACTION_FAILED": status.HTTP_502_BAD_GATEWAY,
    "MENU_IMPORT_INVALID_ROW": status.HTTP_400_BAD_REQUEST,
    # Shared idempotency infrastructure (Sprint 5, Step 4.0) additions:
    "IDEMPOTENCY_KEY_CONFLICT": status.HTTP_409_CONFLICT,
    "IDEMPOTENT_REQUEST_IN_PROGRESS": status.HTTP_409_CONFLICT,
    # MenuItemBranchPrice/MenuItemAvailability (Sprint 5, Step 4.10) additions:
    "EFFECTIVE_WINDOW_OVERLAP": status.HTTP_409_CONFLICT,
    # Reservation (Sprint 5, Step 4.11) additions:
    "RESERVATION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    # Operations module, Order + Kitchen slice (Sprint 7, Step 3) additions:
    "ORDER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_ORDER_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "ORDER_HAS_NO_ITEMS": status.HTTP_409_CONFLICT,
    "ORDER_ITEM_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_ORDER_ITEM_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "MENU_ITEM_NOT_AVAILABLE": status.HTTP_409_CONFLICT,
    "TAB_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_TAB_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "KITCHEN_TICKET_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_KITCHEN_TICKET_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "KITCHEN_ITEM_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_KITCHEN_ITEM_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    # Operations module, Billing + Payments + Ledger slice (Sprint 7, Step 4) additions:
    "BILL_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "BILL_ALREADY_CLOSED": status.HTTP_409_CONFLICT,
    "BILL_ALREADY_EXISTS": status.HTTP_409_CONFLICT,
    "DISCOUNT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "IMPLAUSIBLE_TAX_RATE": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "ADJUSTMENT_APPROVAL_REQUIRED": status.HTTP_409_CONFLICT,
    "TIP_ADJUSTMENT_NOT_SUPPORTED": status.HTTP_409_CONFLICT,
    "PAYMENT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_PAYMENT_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "OVERPAYMENT": status.HTTP_409_CONFLICT,
    "REFUND_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_REFUND_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "REFUND_EXCEEDS_PAYMENT": status.HTTP_409_CONFLICT,
    "CASH_DRAWER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_CASH_DRAWER_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "CASH_DRAWER_ALREADY_OPEN": status.HTTP_409_CONFLICT,
    # Operations module, Inventory + Recipe slice (Sprint 7, Step 5) additions:
    "RECIPE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVENTORY_CATEGORY_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVENTORY_CATEGORY_NAME_CONFLICT": status.HTTP_409_CONFLICT,
    "INVENTORY_ITEM_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVENTORY_ITEM_NAME_CONFLICT": status.HTTP_409_CONFLICT,
    "INSUFFICIENT_STOCK": status.HTTP_409_CONFLICT,
    "STOCK_ADJUSTMENT_REQUIRES_REASON": status.HTTP_422_UNPROCESSABLE_ENTITY,
    # Operations module, Purchasing slice (Sprint 7, Step 6) additions:
    "SUPPLIER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "SUPPLIER_NAME_CONFLICT": status.HTTP_409_CONFLICT,
    "PURCHASE_ORDER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_PURCHASE_ORDER_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
    "PURCHASE_ORDER_HAS_NO_ITEMS": status.HTTP_409_CONFLICT,
    "PURCHASE_ORDER_ITEM_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_GOODS_RECEIPT_STATUS_TRANSITION": status.HTTP_409_CONFLICT,
}

_DEFAULT_STATUS = status.HTTP_422_UNPROCESSABLE_ENTITY


def _format_validation_message(exc: RequestValidationError) -> str:
    """Collapses Pydantic's own list-of-error-objects shape into one
    human-readable string -- the envelope's ``message`` field is a
    plain string everywhere else in this API, and inventing a second,
    structured error shape just for this one status code would be a
    bigger contract change than the actual problem (a raw, differently
    shaped ``{"detail": [...]}`` body) calls for.

    A custom ``raise ValueError(...)`` inside a validator (Pydantic's
    ``"value_error"`` error type) already carries a complete,
    human-authored sentence -- Pydantic just prefixes it with "Value
    error, ". Showing that sentence alone, instead of a
    "body.entries.3: Value error, ..." fragment that means nothing
    outside a debugger, is strictly better for every hand-written
    validator message in this API, not just one endpoint's. Every
    other error type (missing field, wrong type, ...) keeps the
    original ``location: message`` shape, since those messages aren't
    already a complete sentence on their own."""
    parts = []
    for error in exc.errors():
        if error["type"] == "value_error":
            parts.append(str(error["msg"]).removeprefix("Value error, "))
        else:
            location = ".".join(str(segment) for segment in error["loc"])
            parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts) if parts else "Request validation failed."


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

    @app.exception_handler(OperationsDomainError)
    async def handle_operations_domain_error(
        request: Request, exc: OperationsDomainError
    ) -> JSONResponse:
        http_status, body = build_error_response(exc)
        return JSONResponse(status_code=http_status, content=body)

    @app.exception_handler(IdempotencyError)
    async def handle_idempotency_error(request: Request, exc: IdempotencyError) -> JSONResponse:
        http_status, body = build_error_response(exc)
        return JSONResponse(status_code=http_status, content=body)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        envelope = ApiErrorResponse(
            error=ApiErrorDetail(code="VALIDATION_ERROR", message=_format_validation_message(exc))
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
