"""ModifierGroup CRUD endpoints (Sprint 5 Step 4.9).

Restaurant Platform Architecture SS7's ``POST``/``GET``/``PATCH
/api/v1/modifier-groups`` row. ``ModifierGroup`` has no FK parent
(Data Architecture v2.0 Group F -- it belongs directly to the tenant),
so this router's collection path is flat, mirroring
``RestaurantRouter``'s own shape rather than the nested
``TableZoneRouter``/``MenuCategoryRouter`` pattern.

No branch dimension either, so every gate is the plain tenant-wide
``require_permission("menu.read"/"menu.manage")`` -- the same shape
``MenuCategoryRouter``'s gates use for the same reason.

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
    CreateModifierGroupRequestDTO,
    ModifierGroupDTO,
    UpdateModifierGroupRequestDTO,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CreateModifierGroupUseCaseDep,
    GetModifierGroupUseCaseDep,
    IdempotencyGuardDep,
    ListModifierGroupsUseCaseDep,
    RequireMenuManageDep,
    RequireMenuReadDep,
    UpdateModifierGroupUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.modifier_group_schemas import (
    CreateModifierGroupRequestSchema,
    ModifierGroupResponseSchema,
    UpdateModifierGroupRequestSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["modifier-groups"])

ModifierGroupIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _modifier_group_to_schema(dto: ModifierGroupDTO) -> ModifierGroupResponseSchema:
    return ModifierGroupResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        name=dto.name,
        selection_type=dto.selection_type,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/modifier-groups",
    response_model=ApiResponse[ModifierGroupResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_modifier_group(
    body: CreateModifierGroupRequestSchema,
    principal: RequireMenuManageDep,
    use_case: CreateModifierGroupUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateModifierGroupRequestDTO(name=body.name, selection_type=body.selection_type.value),
        )
        response = ApiResponse(data=_modifier_group_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(body.model_dump(mode="json")),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.get(
    "/api/v1/modifier-groups", response_model=ApiResponse[list[ModifierGroupResponseSchema]]
)
async def list_modifier_groups(
    principal: RequireMenuReadDep,
    use_case: ListModifierGroupsUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[ModifierGroupResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_modifier_group_to_schema(g) for g in result.modifier_groups],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/modifier-groups/{modifier_group_id}",
    response_model=ApiResponse[ModifierGroupResponseSchema],
)
async def get_modifier_group(
    modifier_group_id: ModifierGroupIdPath,
    principal: RequireMenuReadDep,
    use_case: GetModifierGroupUseCaseDep,
) -> ApiResponse[ModifierGroupResponseSchema]:
    result = await use_case.execute(principal.tenant_id, modifier_group_id)
    return ApiResponse(data=_modifier_group_to_schema(result))


@router.patch(
    "/api/v1/modifier-groups/{modifier_group_id}",
    response_model=ApiResponse[ModifierGroupResponseSchema],
)
async def update_modifier_group(
    modifier_group_id: ModifierGroupIdPath,
    body: UpdateModifierGroupRequestSchema,
    principal: RequireMenuManageDep,
    use_case: UpdateModifierGroupUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            UpdateModifierGroupRequestDTO(
                modifier_group_id=modifier_group_id,
                name=body.name,
                selection_type=body.selection_type.value,
            ),
        )
        response = ApiResponse(data=_modifier_group_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"modifierGroupId": modifier_group_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
