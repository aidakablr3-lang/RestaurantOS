"""Modifier CRUD endpoints (Sprint 5 Step 4.9).

Restaurant Platform Architecture SS7's ``POST``/``GET``/``PATCH
/api/v1/modifier-groups/{id}/modifiers`` row, kept nested under
``modifier_group_id`` throughout -- ``modifier_group_id`` is scope (the
URL's own path parameter), never an editable body field, mirroring
``MenuItemRouter``'s own treatment of ``menu_category_id`` (see
``update_modifier.py``'s docstring for the full reasoning).

The list route is deliberately unpaginated -- ``ModifierRepository.
list_for_group`` has no ``offset``/``limit``, matching
``QRCodeRouter``'s own list route shape (no ``PaginationMeta``).

No branch dimension, so every gate is the plain tenant-wide
``require_permission("menu.read"/"menu.manage")``.

Idempotency mirrors every other mutating router in this module: an
optional ``Idempotency-Key`` header on the two mutating routes
(create, update), opt-in, only the success path cached.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateModifierRequestDTO,
    ModifierDTO,
    UpdateModifierRequestDTO,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CreateModifierUseCaseDep,
    GetModifierUseCaseDep,
    IdempotencyGuardDep,
    ListModifiersUseCaseDep,
    RequireMenuManageDep,
    RequireMenuReadDep,
    UpdateModifierUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.modifier_schemas import (
    CreateModifierRequestSchema,
    ModifierResponseSchema,
    UpdateModifierRequestSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["modifiers"])

ModifierGroupIdPath = Annotated[str, Path(min_length=26, max_length=26)]
ModifierIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _modifier_to_schema(dto: ModifierDTO) -> ModifierResponseSchema:
    return ModifierResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        modifier_group_id=dto.modifier_group_id,
        name=dto.name,
        price_delta=dto.price_delta,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/modifier-groups/{modifier_group_id}/modifiers",
    response_model=ApiResponse[ModifierResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_modifier(
    modifier_group_id: ModifierGroupIdPath,
    body: CreateModifierRequestSchema,
    principal: RequireMenuManageDep,
    use_case: CreateModifierUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateModifierRequestDTO(
                modifier_group_id=modifier_group_id,
                name=body.name,
                price_delta=body.price_delta,
            ),
        )
        response = ApiResponse(data=_modifier_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

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


@router.get(
    "/api/v1/modifier-groups/{modifier_group_id}/modifiers",
    response_model=ApiResponse[list[ModifierResponseSchema]],
)
async def list_modifiers(
    modifier_group_id: ModifierGroupIdPath,
    principal: RequireMenuReadDep,
    use_case: ListModifiersUseCaseDep,
) -> ApiResponse[list[ModifierResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, modifier_group_id)
    return ApiResponse(data=[_modifier_to_schema(m) for m in result])


@router.get(
    "/api/v1/modifier-groups/{modifier_group_id}/modifiers/{modifier_id}",
    response_model=ApiResponse[ModifierResponseSchema],
)
async def get_modifier(
    modifier_group_id: ModifierGroupIdPath,
    modifier_id: ModifierIdPath,
    principal: RequireMenuReadDep,
    use_case: GetModifierUseCaseDep,
) -> ApiResponse[ModifierResponseSchema]:
    result = await use_case.execute(principal.tenant_id, modifier_group_id, modifier_id)
    return ApiResponse(data=_modifier_to_schema(result))


@router.patch(
    "/api/v1/modifier-groups/{modifier_group_id}/modifiers/{modifier_id}",
    response_model=ApiResponse[ModifierResponseSchema],
)
async def update_modifier(
    modifier_group_id: ModifierGroupIdPath,
    modifier_id: ModifierIdPath,
    body: UpdateModifierRequestSchema,
    principal: RequireMenuManageDep,
    use_case: UpdateModifierUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            UpdateModifierRequestDTO(
                modifier_id=modifier_id,
                modifier_group_id=modifier_group_id,
                name=body.name,
                price_delta=body.price_delta,
            ),
        )
        response = ApiResponse(data=_modifier_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "modifierGroupId": modifier_group_id,
                    "modifierId": modifier_id,
                    **body.model_dump(mode="json"),
                }
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
