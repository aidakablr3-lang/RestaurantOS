"""Table CRUD + status-change endpoints (Sprint 5 Step 4.5).

Restaurant Platform Architecture SS7's ``POST``/``GET``/``PATCH``
``/api/v1/branches/{branch_id}/tables`` row (expanded to the same
explicit collection-vs-item route shape TableZone already uses, for
the same reason -- every CRUD route reuses ``require_branch_permission``
by staying nested under ``branch_id``) plus the one route SS7 puts at
a deliberately *flat* path, ``POST /api/v1/tables/{id}/status`` --
"the one endpoint a future Edge app's sync engine will eventually call
through ``/sync/push`` instead of this direct path". That route has no
``branch_id`` in its URL, so it is gated differently: a coarse
``require_permission_at_any_scope("table.manage")`` here, plus
``ChangeTableStatusUseCase``'s own fine-grained
``resolve_and_authorize_branch`` call once the table (and therefore
its real ``branch_id``) is loaded -- see that use case's docstring.

Every route resolves through a tenant-scoped repository lookup before
anything else -- a branch, table zone, or table that exists but
belongs to another tenant (or, for a single table, a different branch)
is a 404, identical to one that does not exist at all, never a
distinguishable 403 (no existence leak).

Idempotency mirrors every other mutating router in this module: an
optional ``Idempotency-Key`` header on the three mutating routes
(create, update, status-change), opt-in, only the success path cached.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.restaurant.application.dto import (
    ChangeTableStatusRequestDTO,
    CreateTableRequestDTO,
    TableDTO,
    UpdateTableRequestDTO,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    ChangeTableStatusUseCaseDep,
    CreateTableUseCaseDep,
    GetTableUseCaseDep,
    IdempotencyGuardDep,
    ListTablesUseCaseDep,
    RequireTableManageAtAnyScopeDep,
    RequireTableManageDep,
    RequireTableReadDep,
    UpdateTableUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.table_schemas import (
    ChangeTableStatusRequestSchema,
    CreateTableRequestSchema,
    TableResponseSchema,
    UpdateTableRequestSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["tables"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
TableIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _table_to_schema(dto: TableDTO) -> TableResponseSchema:
    return TableResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        table_zone_id=dto.table_zone_id,
        table_number=dto.table_number,
        capacity=dto.capacity,
        status=dto.status,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/branches/{branch_id}/tables",
    response_model=ApiResponse[TableResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_table(
    branch_id: BranchIdPath,
    body: CreateTableRequestSchema,
    principal: RequireTableManageDep,
    use_case: CreateTableUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateTableRequestDTO(
                branch_id=branch_id,
                table_zone_id=body.table_zone_id,
                table_number=body.table_number,
                capacity=body.capacity,
            ),
        )
        response = ApiResponse(data=_table_to_schema(result))
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
    "/api/v1/branches/{branch_id}/tables",
    response_model=ApiResponse[list[TableResponseSchema]],
)
async def list_tables(
    branch_id: BranchIdPath,
    principal: RequireTableReadDep,
    use_case: ListTablesUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[TableResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, branch_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_table_to_schema(t) for t in result.tables],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/branches/{branch_id}/tables/{table_id}",
    response_model=ApiResponse[TableResponseSchema],
)
async def get_table(
    branch_id: BranchIdPath,
    table_id: TableIdPath,
    principal: RequireTableReadDep,
    use_case: GetTableUseCaseDep,
) -> ApiResponse[TableResponseSchema]:
    result = await use_case.execute(principal.tenant_id, branch_id, table_id)
    return ApiResponse(data=_table_to_schema(result))


@router.patch(
    "/api/v1/branches/{branch_id}/tables/{table_id}",
    response_model=ApiResponse[TableResponseSchema],
)
async def update_table(
    branch_id: BranchIdPath,
    table_id: TableIdPath,
    body: UpdateTableRequestSchema,
    principal: RequireTableManageDep,
    use_case: UpdateTableUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            UpdateTableRequestDTO(
                table_id=table_id,
                branch_id=branch_id,
                table_zone_id=body.table_zone_id,
                table_number=body.table_number,
                capacity=body.capacity,
            ),
        )
        response = ApiResponse(data=_table_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"branchId": branch_id, "tableId": table_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.post(
    "/api/v1/tables/{table_id}/status",
    response_model=ApiResponse[TableResponseSchema],
)
async def change_table_status(
    table_id: TableIdPath,
    body: ChangeTableStatusRequestSchema,
    principal: RequireTableManageAtAnyScopeDep,
    use_case: ChangeTableStatusUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            principal.user_id,
            ChangeTableStatusRequestDTO(table_id=table_id, status=body.status.value),
        )
        response = ApiResponse(data=_table_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"tableId": table_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
