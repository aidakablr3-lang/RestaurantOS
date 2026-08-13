"""Tab create/close endpoints (Sprint 7 Step 3)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.operations.application.dto import CreateTabRequestDTO, TabDTO
from restaurant_os_api.modules.operations.presentation.dependencies import (
    CloseTabUseCaseDep,
    CreateTabUseCaseDep,
    IdempotencyGuardDep,
    RequireOrderManageAtAnyScopeDep,
    RequireOrderManageDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.tab_schemas import (
    CreateTabRequestSchema,
    TabResponseSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["tabs"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
TabIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _tab_to_schema(dto: TabDTO) -> TabResponseSchema:
    return TabResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        status=dto.status,
        opened_at=dto.opened_at,
        created_at=dto.created_at,
        table_id=dto.table_id,
        customer_id=dto.customer_id,
        closed_at=dto.closed_at,
    )


@router.post(
    "/api/v1/branches/{branch_id}/tabs",
    response_model=ApiResponse[TabResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_tab(
    branch_id: BranchIdPath,
    body: CreateTabRequestSchema,
    principal: RequireOrderManageDep,
    use_case: CreateTabUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateTabRequestDTO(branch_id=branch_id, table_id=body.table_id),
        )
        response = ApiResponse(data=_tab_to_schema(result))
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


@router.post("/api/v1/tabs/{tab_id}/close", response_model=ApiResponse[TabResponseSchema])
async def close_tab(
    tab_id: TabIdPath,
    principal: RequireOrderManageAtAnyScopeDep,
    use_case: CloseTabUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(principal.tenant_id, principal.user_id, tab_id)
        response = ApiResponse(data=_tab_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request({"tabId": tab_id, "action": "close"}),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
