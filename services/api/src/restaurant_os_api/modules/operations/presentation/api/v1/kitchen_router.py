"""KitchenTicket/KitchenItem endpoints (Sprint 7 Step 3).

``GET /api/v1/branches/{branch_id}/kitchen-tickets`` stays nested under
``branch_id``. The two status routes are flat -- same coarse
``kitchen.manage`` at any scope + fine-grained
``resolve_and_authorize_branch`` split as Order's own lifecycle routes.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.operations.application.dto import (
    ChangeKitchenItemStatusRequestDTO,
    ChangeKitchenTicketStatusRequestDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    IdempotencyGuardDep,
    ListKitchenTicketsUseCaseDep,
    RequireKitchenManageAtAnyScopeDep,
    RequireKitchenReadDep,
    UpdateKitchenItemStatusUseCaseDep,
    UpdateKitchenTicketStatusUseCaseDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.kitchen_schemas import (
    ChangeKitchenItemStatusRequestSchema,
    ChangeKitchenTicketStatusRequestSchema,
    KitchenItemResponseSchema,
    KitchenTicketResponseSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["kitchen"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
KitchenTicketIdPath = Annotated[str, Path(min_length=26, max_length=26)]
KitchenItemIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _kitchen_ticket_to_schema(dto: Any) -> KitchenTicketResponseSchema:
    return KitchenTicketResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        order_id=dto.order_id,
        station=dto.station,
        status=dto.status,
        created_at=dto.created_at,
        items=[
            KitchenItemResponseSchema(
                id=item.id,
                kitchen_ticket_id=item.kitchen_ticket_id,
                order_item_id=item.order_item_id,
                status=item.status,
                created_at=item.created_at,
            )
            for item in dto.items
        ],
    )


@router.get(
    "/api/v1/branches/{branch_id}/kitchen-tickets",
    response_model=ApiResponse[list[KitchenTicketResponseSchema]],
)
async def list_kitchen_tickets(
    branch_id: BranchIdPath,
    principal: RequireKitchenReadDep,
    use_case: ListKitchenTicketsUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[KitchenTicketResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, branch_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_kitchen_ticket_to_schema(t) for t in result.tickets],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.post(
    "/api/v1/kitchen-tickets/{kitchen_ticket_id}/status",
    response_model=ApiResponse[KitchenTicketResponseSchema],
)
async def change_kitchen_ticket_status(
    kitchen_ticket_id: KitchenTicketIdPath,
    body: ChangeKitchenTicketStatusRequestSchema,
    principal: RequireKitchenManageAtAnyScopeDep,
    use_case: UpdateKitchenTicketStatusUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            principal.user_id,
            ChangeKitchenTicketStatusRequestDTO(
                kitchen_ticket_id=kitchen_ticket_id, status=body.status.value
            ),
        )
        response = ApiResponse(data=_kitchen_ticket_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"kitchenTicketId": kitchen_ticket_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.post(
    "/api/v1/kitchen-items/{kitchen_item_id}/status",
    response_model=ApiResponse[KitchenItemResponseSchema],
)
async def change_kitchen_item_status(
    kitchen_item_id: KitchenItemIdPath,
    body: ChangeKitchenItemStatusRequestSchema,
    principal: RequireKitchenManageAtAnyScopeDep,
    use_case: UpdateKitchenItemStatusUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            principal.user_id,
            ChangeKitchenItemStatusRequestDTO(
                kitchen_item_id=kitchen_item_id, status=body.status.value
            ),
        )
        response = ApiResponse(
            data=KitchenItemResponseSchema(
                id=result.id,
                kitchen_ticket_id=result.kitchen_ticket_id,
                order_item_id=result.order_item_id,
                status=result.status,
                created_at=result.created_at,
            )
        )
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"kitchenItemId": kitchen_item_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
