"""Tenant Administration endpoints — platform-admin only.

Technical Architecture v2.0 SS5.5: URI-based versioning. Every handler
here does exactly one thing: parse, call one use case, shape the
response. Gated on ``require_platform_admin`` at the router level
(approved plan Decision C) — every route below requires
``is_platform_admin=True``, not just some of them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.identity.application.dto import (
    ListTenantsRequestDTO,
    OnboardTenantRequestDTO,
    TenantDTO,
    UpdateTenantRequestDTO,
)
from restaurant_os_api.modules.identity.presentation.dependencies import (
    GetTenantUseCaseDep,
    ListTenantsUseCaseDep,
    OffboardTenantUseCaseDep,
    OnboardTenantUseCaseDep,
    ReactivateTenantUseCaseDep,
    SuspendTenantUseCaseDep,
    UpdateTenantUseCaseDep,
    require_platform_admin,
)
from restaurant_os_api.modules.identity.presentation.schemas.tenant_schemas import (
    OnboardTenantRequestSchema,
    TenantResponseSchema,
    UpdateTenantRequestSchema,
)

router = APIRouter(
    prefix="/api/v1/admin/tenants",
    tags=["tenant-administration"],
    dependencies=[Depends(require_platform_admin)],
)

TenantIdPath = Annotated[str, Path(min_length=26, max_length=26)]


def _to_schema(dto: TenantDTO) -> TenantResponseSchema:
    return TenantResponseSchema(
        id=dto.id,
        legal_name=dto.legal_name,
        display_name=dto.display_name,
        tenant_tier=dto.tenant_tier,
        status=dto.status,
        default_currency_code=dto.default_currency_code,
        metadata=dto.metadata,
        created_at=dto.created_at,
    )


@router.post(
    "", response_model=ApiResponse[TenantResponseSchema], status_code=status.HTTP_201_CREATED
)
async def onboard_tenant(
    body: OnboardTenantRequestSchema, use_case: OnboardTenantUseCaseDep
) -> ApiResponse[TenantResponseSchema]:
    result = await use_case.execute(
        OnboardTenantRequestDTO(
            legal_name=body.legal_name,
            display_name=body.display_name,
            default_currency_code=body.default_currency_code,
        )
    )
    return ApiResponse(data=_to_schema(result))


@router.get("", response_model=ApiResponse[list[TenantResponseSchema]])
async def list_tenants(
    use_case: ListTenantsUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> ApiResponse[list[TenantResponseSchema]]:
    result = await use_case.execute(
        ListTenantsRequestDTO(offset=offset, limit=limit, status=status_filter)
    )
    return ApiResponse(
        data=[_to_schema(t) for t in result.tenants],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get("/{tenant_id}", response_model=ApiResponse[TenantResponseSchema])
async def get_tenant(
    tenant_id: TenantIdPath, use_case: GetTenantUseCaseDep
) -> ApiResponse[TenantResponseSchema]:
    result = await use_case.execute(tenant_id)
    return ApiResponse(data=_to_schema(result))


@router.patch("/{tenant_id}", response_model=ApiResponse[TenantResponseSchema])
async def update_tenant(
    tenant_id: TenantIdPath, body: UpdateTenantRequestSchema, use_case: UpdateTenantUseCaseDep
) -> ApiResponse[TenantResponseSchema]:
    result = await use_case.execute(
        UpdateTenantRequestDTO(
            tenant_id=tenant_id, display_name=body.display_name, metadata=body.metadata
        )
    )
    return ApiResponse(data=_to_schema(result))


@router.post("/{tenant_id}/suspend", response_model=ApiResponse[TenantResponseSchema])
async def suspend_tenant(
    tenant_id: TenantIdPath, use_case: SuspendTenantUseCaseDep
) -> ApiResponse[TenantResponseSchema]:
    result = await use_case.execute(tenant_id)
    return ApiResponse(data=_to_schema(result))


@router.post("/{tenant_id}/reactivate", response_model=ApiResponse[TenantResponseSchema])
async def reactivate_tenant(
    tenant_id: TenantIdPath, use_case: ReactivateTenantUseCaseDep
) -> ApiResponse[TenantResponseSchema]:
    result = await use_case.execute(tenant_id)
    return ApiResponse(data=_to_schema(result))


@router.post("/{tenant_id}/offboard", response_model=ApiResponse[TenantResponseSchema])
async def offboard_tenant(
    tenant_id: TenantIdPath, use_case: OffboardTenantUseCaseDep
) -> ApiResponse[TenantResponseSchema]:
    result = await use_case.execute(tenant_id)
    return ApiResponse(data=_to_schema(result))
