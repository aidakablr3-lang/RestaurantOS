"""Guest QR ordering routes (guest ordering gap fix).

The unauthenticated counterpart to ``order_router.py`` -- no
``AuthenticatedPrincipalDep``, no RBAC, no ``Idempotency-Key``-guarded
staff action. Every route is keyed by the same ``{token}`` path segment
``GET /api/v1/qr/{token}`` (ADR 0001) already established, and every
route re-resolves it via ``GuestResolveQRCodeUseCaseDep`` before doing
anything else -- the token, revalidated per call, *is* the guest's only
credential (see ``_guest_order_guard``'s own docstring for the full
rationale). Resolution failure collapses into the exact same two
outcomes ``qr_resolution_router.py`` already established: token
not-found/revoked is a generic 404 ``{"error": "not_found"}``
(enumeration protection, ADR 0001), rate-limit rejection is 429
``{"error": "rate_limited"}`` -- both bodies reused byte-for-byte so a
scanning client can't distinguish "this route is guest-order-specific"
from "the token itself is bad" by response shape.

Everything past resolution uses the standard ``ApiResponse[T]`` envelope
like every other route in this codebase -- only the token-resolution
step itself inherits ADR 0001's minimal contract, not the rest of this
feature (``GuestMenuResponseSchema``'s own docstring explains why).

No approval gate, no in-app payment -- both disclosed, deliberate scope
decisions for this feature (guest orders fire straight to the kitchen;
the guest pays at the table through the existing staff-side billing
flow), not omissions.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Request, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.operations.application.dto import (
    AddOrderItemRequestDTO,
    CreateOrderRequestDTO,
    OrderDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    CreateOrderUseCaseDep,
    GuestAddOrderItemUseCaseDep,
    GuestGetOrderUseCaseDep,
    GuestSubmitOrderUseCaseDep,
    IdempotencyGuardDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.order_schemas import (
    AddOrderItemRequestSchema,
    OrderItemResponseSchema,
    OrderResponseSchema,
)
from restaurant_os_api.modules.restaurant.application.dto import QRCodeResolutionDTO
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    GuestGetMenuUseCaseDep,
    GuestResolveQRCodeUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.guest_menu_schemas import (
    GuestMenuCategoryResponseSchema,
    GuestMenuItemResponseSchema,
    GuestMenuResponseSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request
from restaurant_os_api.platform.rate_limiting import RateLimitExceededError

router = APIRouter(tags=["guest-ordering"])

TokenPath = Annotated[str, Path()]
OrderIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]

_NOT_FOUND_BODY = {"error": "not_found"}
_RATE_LIMITED_BODY = {"error": "rate_limited"}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


async def _resolve(
    token: str, request: Request, use_case: GuestResolveQRCodeUseCaseDep
) -> QRCodeResolutionDTO | JSONResponse:
    try:
        result = await use_case.execute(token, _client_ip(request))
    except RateLimitExceededError:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=_RATE_LIMITED_BODY
        )
    if result is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=_NOT_FOUND_BODY)
    return result


def _order_to_schema(dto: OrderDTO) -> OrderResponseSchema:
    return OrderResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        order_source=dto.order_source,
        status=dto.status,
        subtotal_amount=dto.subtotal_amount,
        tax_amount=dto.tax_amount,
        total_amount=dto.total_amount,
        currency_code=dto.currency_code,
        opened_at=dto.opened_at,
        created_at=dto.created_at,
        items=[
            OrderItemResponseSchema(
                id=item.id,
                order_id=item.order_id,
                menu_item_id=item.menu_item_id,
                quantity=item.quantity,
                unit_price_amount=item.unit_price_amount,
                line_status=item.line_status,
                created_at=item.created_at,
                modifiers_snapshot=item.modifiers_snapshot,
                recipe_cost_snapshot=item.recipe_cost_snapshot,
            )
            for item in dto.items
        ],
        table_id=dto.table_id,
        tab_id=dto.tab_id,
        customer_id=dto.customer_id,
        closed_at=dto.closed_at,
        origin_device_id=dto.origin_device_id,
        item_count=dto.item_count,
    )


@router.get("/api/v1/qr/{token}/menu", response_model=ApiResponse[GuestMenuResponseSchema])
async def get_guest_menu(
    token: TokenPath,
    request: Request,
    resolve_use_case: GuestResolveQRCodeUseCaseDep,
    use_case: GuestGetMenuUseCaseDep,
) -> JSONResponse:
    resolved = await _resolve(token, request, resolve_use_case)
    if isinstance(resolved, JSONResponse):
        return resolved

    menu = await use_case.execute(resolved.tenant_id, resolved.branch_id, resolved.table_id)
    body = GuestMenuResponseSchema(
        branch_id=menu.branch_id,
        table_id=menu.table_id,
        restaurant_name=menu.restaurant_name,
        branch_name=menu.branch_name,
        table_number=menu.table_number,
        categories=[
            GuestMenuCategoryResponseSchema(
                id=category.id,
                name=category.name,
                display_order=category.display_order,
                items=[
                    GuestMenuItemResponseSchema(
                        id=item.id,
                        name=item.name,
                        price_amount=item.price_amount,
                        currency_code=item.currency_code,
                    )
                    for item in category.items
                ],
            )
            for category in menu.categories
        ],
    )
    response = ApiResponse(data=body)
    return JSONResponse(
        status_code=status.HTTP_200_OK, content=response.model_dump(mode="json", by_alias=True)
    )


@router.post(
    "/api/v1/qr/{token}/orders",
    response_model=ApiResponse[OrderResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_guest_order(
    token: TokenPath,
    request: Request,
    resolve_use_case: GuestResolveQRCodeUseCaseDep,
    use_case: CreateOrderUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    resolved = await _resolve(token, request, resolve_use_case)
    if isinstance(resolved, JSONResponse):
        return resolved

    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            resolved.tenant_id,
            CreateOrderRequestDTO(
                branch_id=resolved.branch_id,
                order_source="qr",
                table_id=resolved.table_id,
            ),
        )
        response = ApiResponse(data=_order_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=resolved.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request({"token": token}),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.post(
    "/api/v1/qr/{token}/orders/{order_id}/items",
    response_model=ApiResponse[OrderResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def add_guest_order_item(
    token: TokenPath,
    order_id: OrderIdPath,
    body: AddOrderItemRequestSchema,
    request: Request,
    resolve_use_case: GuestResolveQRCodeUseCaseDep,
    use_case: GuestAddOrderItemUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    resolved = await _resolve(token, request, resolve_use_case)
    if isinstance(resolved, JSONResponse):
        return resolved

    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            resolved.tenant_id,
            resolved.branch_id,
            resolved.table_id,
            AddOrderItemRequestDTO(
                order_id=order_id,
                menu_item_id=body.menu_item_id,
                quantity=body.quantity,
                modifiers_snapshot=body.modifiers_snapshot,
            ),
        )
        response = ApiResponse(data=_order_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=resolved.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"orderId": order_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.post(
    "/api/v1/qr/{token}/orders/{order_id}/submit",
    response_model=ApiResponse[OrderResponseSchema],
)
async def submit_guest_order(
    token: TokenPath,
    order_id: OrderIdPath,
    request: Request,
    resolve_use_case: GuestResolveQRCodeUseCaseDep,
    use_case: GuestSubmitOrderUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    resolved = await _resolve(token, request, resolve_use_case)
    if isinstance(resolved, JSONResponse):
        return resolved

    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            resolved.tenant_id, resolved.branch_id, resolved.table_id, order_id
        )
        response = ApiResponse(data=_order_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=resolved.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request({"orderId": order_id, "action": "submit"}),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.get(
    "/api/v1/qr/{token}/orders/{order_id}",
    response_model=ApiResponse[OrderResponseSchema],
)
async def get_guest_order(
    token: TokenPath,
    order_id: OrderIdPath,
    request: Request,
    resolve_use_case: GuestResolveQRCodeUseCaseDep,
    use_case: GuestGetOrderUseCaseDep,
) -> JSONResponse:
    resolved = await _resolve(token, request, resolve_use_case)
    if isinstance(resolved, JSONResponse):
        return resolved

    result = await use_case.execute(
        resolved.tenant_id, resolved.branch_id, resolved.table_id, order_id
    )
    response = ApiResponse(data=_order_to_schema(result))
    return JSONResponse(
        status_code=status.HTTP_200_OK, content=response.model_dump(mode="json", by_alias=True)
    )
