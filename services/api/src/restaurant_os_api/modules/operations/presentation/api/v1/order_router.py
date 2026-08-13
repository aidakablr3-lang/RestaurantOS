"""Order CRUD + item/fire/close/void endpoints (Sprint 7 Step 3).

``POST``/``GET`` ``/api/v1/branches/{branch_id}/orders`` (+ item GET)
stay nested under ``branch_id`` so ``require_branch_permission`` can
gate them directly. ``items``/``fire``/``close``/``void``/``items/
{order_item_id}/void`` are flat (Architecture doc SS6) -- gated by a
coarse ``require_permission_at_any_scope("order.manage")`` here, plus
each use case's own fine-grained ``resolve_and_authorize_branch`` call
once the order (and therefore its real ``branch_id``) is loaded.

``items/{order_item_id}/void`` is the line-level counterpart to
``void`` -- pre-fire only, see ``VoidOrderItemUseCase``'s own
docstring for why a fired line has no void route here.

Every route resolves through a tenant-scoped repository lookup before
anything else -- cross-scope is a 404, never a distinguishable 403, no
existence leak. Idempotency mirrors every other mutating router in this
codebase: an optional ``Idempotency-Key`` header, opt-in, only the
success path cached.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.operations.application.dto import (
    AddOrderItemRequestDTO,
    CreateOrderRequestDTO,
    OrderDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    AddOrderItemUseCaseDep,
    CloseOrderUseCaseDep,
    CreateOrderUseCaseDep,
    FireOrderUseCaseDep,
    GetOrderUseCaseDep,
    IdempotencyGuardDep,
    ListOrdersUseCaseDep,
    RequireOrderManageAtAnyScopeDep,
    RequireOrderManageDep,
    RequireOrderReadDep,
    VoidOrderItemUseCaseDep,
    VoidOrderUseCaseDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.order_schemas import (
    AddOrderItemRequestSchema,
    CreateOrderRequestSchema,
    OrderItemResponseSchema,
    OrderResponseSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["orders"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
OrderIdPath = Annotated[str, Path(min_length=26, max_length=26)]
OrderItemIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


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


@router.post(
    "/api/v1/branches/{branch_id}/orders",
    response_model=ApiResponse[OrderResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    branch_id: BranchIdPath,
    body: CreateOrderRequestSchema,
    principal: RequireOrderManageDep,
    use_case: CreateOrderUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateOrderRequestDTO(
                branch_id=branch_id,
                order_source=body.order_source.value,
                table_id=body.table_id,
                tab_id=body.tab_id,
                origin_device_id=body.origin_device_id,
            ),
        )
        response = ApiResponse(data=_order_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"branchId": branch_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.get(
    "/api/v1/branches/{branch_id}/orders",
    response_model=ApiResponse[list[OrderResponseSchema]],
)
async def list_orders(
    branch_id: BranchIdPath,
    principal: RequireOrderReadDep,
    use_case: ListOrdersUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    table_id: Annotated[str | None, Query(alias="tableId", min_length=26, max_length=26)] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> ApiResponse[list[OrderResponseSchema]]:
    result = await use_case.execute(
        principal.tenant_id,
        branch_id,
        offset=offset,
        limit=limit,
        table_id=table_id,
        status=status_filter,
    )
    return ApiResponse(
        data=[_order_to_schema(o) for o in result.orders],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/branches/{branch_id}/orders/{order_id}",
    response_model=ApiResponse[OrderResponseSchema],
)
async def get_order(
    branch_id: BranchIdPath,
    order_id: OrderIdPath,
    principal: RequireOrderReadDep,
    use_case: GetOrderUseCaseDep,
) -> ApiResponse[OrderResponseSchema]:
    result = await use_case.execute(principal.tenant_id, branch_id, order_id)
    return ApiResponse(data=_order_to_schema(result))


@router.post(
    "/api/v1/orders/{order_id}/items",
    response_model=ApiResponse[OrderResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def add_order_item(
    order_id: OrderIdPath,
    body: AddOrderItemRequestSchema,
    principal: RequireOrderManageAtAnyScopeDep,
    use_case: AddOrderItemUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            principal.user_id,
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
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"orderId": order_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


async def _run_lifecycle_action(
    *,
    order_id: str,
    principal: Any,
    use_case: Any,
    idempotency_guard: Any,
    idempotency_key: str | None,
    action_name: str,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(principal.tenant_id, principal.user_id, order_id)
        response = ApiResponse(data=_order_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request({"orderId": order_id, "action": action_name}),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.post("/api/v1/orders/{order_id}/fire", response_model=ApiResponse[OrderResponseSchema])
async def fire_order(
    order_id: OrderIdPath,
    principal: RequireOrderManageAtAnyScopeDep,
    use_case: FireOrderUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    return await _run_lifecycle_action(
        order_id=order_id,
        principal=principal,
        use_case=use_case,
        idempotency_guard=idempotency_guard,
        idempotency_key=idempotency_key,
        action_name="fire",
    )


@router.post("/api/v1/orders/{order_id}/close", response_model=ApiResponse[OrderResponseSchema])
async def close_order(
    order_id: OrderIdPath,
    principal: RequireOrderManageAtAnyScopeDep,
    use_case: CloseOrderUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    return await _run_lifecycle_action(
        order_id=order_id,
        principal=principal,
        use_case=use_case,
        idempotency_guard=idempotency_guard,
        idempotency_key=idempotency_key,
        action_name="close",
    )


@router.post("/api/v1/orders/{order_id}/void", response_model=ApiResponse[OrderResponseSchema])
async def void_order(
    order_id: OrderIdPath,
    principal: RequireOrderManageAtAnyScopeDep,
    use_case: VoidOrderUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    return await _run_lifecycle_action(
        order_id=order_id,
        principal=principal,
        use_case=use_case,
        idempotency_guard=idempotency_guard,
        idempotency_key=idempotency_key,
        action_name="void",
    )


@router.post(
    "/api/v1/orders/{order_id}/items/{order_item_id}/void",
    response_model=ApiResponse[OrderResponseSchema],
)
async def void_order_item(
    order_id: OrderIdPath,
    order_item_id: OrderItemIdPath,
    principal: RequireOrderManageAtAnyScopeDep,
    use_case: VoidOrderItemUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id, principal.user_id, order_id, order_item_id
        )
        response = ApiResponse(data=_order_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"orderId": order_id, "orderItemId": order_item_id, "action": "void_item"}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
