"""Discount CRUD endpoints (Sprint 7 Step 4) -- tenant-wide, flat, the
same shape ``ModifierGroupRouter`` uses."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.operations.application.dto import (
    CreateDiscountRequestDTO,
    DiscountDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    CreateDiscountUseCaseDep,
    ListDiscountsUseCaseDep,
    RequireBillingManageTenantWideDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.discount_schemas import (
    CreateDiscountRequestSchema,
    DiscountResponseSchema,
)

router = APIRouter(tags=["discounts"])


def _discount_to_schema(dto: DiscountDTO) -> DiscountResponseSchema:
    return DiscountResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        name=dto.name,
        discount_type=dto.discount_type,
        value=dto.value,
        requires_approval=dto.requires_approval,
        created_at=dto.created_at,
        max_value=dto.max_value,
        active_from=dto.active_from,
        active_to=dto.active_to,
    )


@router.post(
    "/api/v1/discounts",
    response_model=ApiResponse[DiscountResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_discount(
    body: CreateDiscountRequestSchema,
    principal: RequireBillingManageTenantWideDep,
    use_case: CreateDiscountUseCaseDep,
) -> ApiResponse[DiscountResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        CreateDiscountRequestDTO(
            name=body.name,
            discount_type=body.discount_type.value,
            value=body.value,
            requires_approval=body.requires_approval,
            max_value=body.max_value,
            active_from=body.active_from,
            active_to=body.active_to,
        ),
    )
    return ApiResponse(data=_discount_to_schema(result))


@router.get("/api/v1/discounts", response_model=ApiResponse[list[DiscountResponseSchema]])
async def list_discounts(
    principal: RequireBillingManageTenantWideDep,
    use_case: ListDiscountsUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[DiscountResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_discount_to_schema(d) for d in result.discounts],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )
