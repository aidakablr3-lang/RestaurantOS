"""TableZone (Dining Areas) CRUD endpoints (Sprint 5 Step 4.4).

Restaurant Platform Architecture SS7's ``POST``/``GET``/``PATCH``
``/api/v1/branches/{branch_id}/table-zones`` row, expanded to the same
explicit collection-vs-item route shape already used for every other
entity with a ``PATCH`` in that table (Restaurant, Branch): ``POST``
(create) and ``GET`` (paginated list) against the collection path,
``GET``/``PATCH /table-zones/{id}`` against a single item -- kept
nested under ``branch_id`` throughout (rather than a flat
``/api/v1/table-zones/{id}``) specifically so every route can reuse
``require_branch_permission`` exactly as built, gating on the URL's
own ``branch_id`` path parameter, with no new authorization shape for
a body- or item-scoped ``branch_id``.

Every route resolves through a tenant-scoped repository lookup before
anything else -- a branch or table zone that exists but belongs to
another tenant (or, for a single item, a different branch) is a 404,
identical to one that does not exist at all, never a distinguishable
403 (no existence leak).

Idempotency mirrors every other mutating router in this module: an
optional ``Idempotency-Key`` header on the two mutating routes
(create, update), opt-in, only the success path cached.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateTableZoneRequestDTO,
    TableZoneDTO,
    UpdateTableZoneRequestDTO,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CreateTableZoneUseCaseDep,
    GetTableZoneUseCaseDep,
    IdempotencyGuardDep,
    ListTableZonesUseCaseDep,
    RequireTableManageDep,
    RequireTableReadDep,
    UpdateTableZoneUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.table_zone_schemas import (
    CreateTableZoneRequestSchema,
    TableZoneResponseSchema,
    UpdateTableZoneRequestSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["table-zones"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
TableZoneIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _table_zone_to_schema(dto: TableZoneDTO) -> TableZoneResponseSchema:
    return TableZoneResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        name=dto.name,
        display_order=dto.display_order,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/branches/{branch_id}/table-zones",
    response_model=ApiResponse[TableZoneResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_table_zone(
    branch_id: BranchIdPath,
    body: CreateTableZoneRequestSchema,
    principal: RequireTableManageDep,
    use_case: CreateTableZoneUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateTableZoneRequestDTO(
                branch_id=branch_id, name=body.name, display_order=body.display_order
            ),
        )
        response = ApiResponse(data=_table_zone_to_schema(result))
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
    "/api/v1/branches/{branch_id}/table-zones",
    response_model=ApiResponse[list[TableZoneResponseSchema]],
)
async def list_table_zones(
    branch_id: BranchIdPath,
    principal: RequireTableReadDep,
    use_case: ListTableZonesUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[TableZoneResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, branch_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_table_zone_to_schema(tz) for tz in result.table_zones],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/branches/{branch_id}/table-zones/{table_zone_id}",
    response_model=ApiResponse[TableZoneResponseSchema],
)
async def get_table_zone(
    branch_id: BranchIdPath,
    table_zone_id: TableZoneIdPath,
    principal: RequireTableReadDep,
    use_case: GetTableZoneUseCaseDep,
) -> ApiResponse[TableZoneResponseSchema]:
    result = await use_case.execute(principal.tenant_id, branch_id, table_zone_id)
    return ApiResponse(data=_table_zone_to_schema(result))


@router.patch(
    "/api/v1/branches/{branch_id}/table-zones/{table_zone_id}",
    response_model=ApiResponse[TableZoneResponseSchema],
)
async def update_table_zone(
    branch_id: BranchIdPath,
    table_zone_id: TableZoneIdPath,
    body: UpdateTableZoneRequestSchema,
    principal: RequireTableManageDep,
    use_case: UpdateTableZoneUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            UpdateTableZoneRequestDTO(
                table_zone_id=table_zone_id,
                branch_id=branch_id,
                name=body.name,
                display_order=body.display_order,
            ),
        )
        response = ApiResponse(data=_table_zone_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "branchId": branch_id,
                    "tableZoneId": table_zone_id,
                    **body.model_dump(mode="json"),
                }
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
