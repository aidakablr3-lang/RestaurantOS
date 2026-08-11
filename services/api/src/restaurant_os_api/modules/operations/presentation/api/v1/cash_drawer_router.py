"""CashDrawer open/close endpoints (Sprint 7 Step 4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, status

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.operations.application.dto import (
    CashDrawerDTO,
    CloseCashDrawerRequestDTO,
    OpenCashDrawerRequestDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    CloseCashDrawerUseCaseDep,
    OpenCashDrawerUseCaseDep,
    RequireBillingManageAtAnyScopeDep,
    RequireBillingManageDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.cash_drawer_schemas import (
    CashDrawerResponseSchema,
    CloseCashDrawerRequestSchema,
    OpenCashDrawerRequestSchema,
)

router = APIRouter(tags=["cash-drawers"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
CashDrawerIdPath = Annotated[str, Path(min_length=26, max_length=26)]


def _cash_drawer_to_schema(dto: CashDrawerDTO) -> CashDrawerResponseSchema:
    return CashDrawerResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        status=dto.status,
        opening_float_amount=dto.opening_float_amount,
        opened_at=dto.opened_at,
        created_at=dto.created_at,
        terminal_id=dto.terminal_id,
        closing_counted_amount=dto.closing_counted_amount,
        closed_at=dto.closed_at,
        expected_cash_amount=dto.expected_cash_amount,
        variance_amount=dto.variance_amount,
    )


@router.post(
    "/api/v1/branches/{branch_id}/cash-drawers",
    response_model=ApiResponse[CashDrawerResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def open_cash_drawer(
    branch_id: BranchIdPath,
    body: OpenCashDrawerRequestSchema,
    principal: RequireBillingManageDep,
    use_case: OpenCashDrawerUseCaseDep,
) -> ApiResponse[CashDrawerResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        OpenCashDrawerRequestDTO(
            branch_id=branch_id,
            opening_float_amount=body.opening_float_amount,
            terminal_id=body.terminal_id,
        ),
    )
    return ApiResponse(data=_cash_drawer_to_schema(result))


@router.post(
    "/api/v1/cash-drawers/{cash_drawer_id}/close",
    response_model=ApiResponse[CashDrawerResponseSchema],
)
async def close_cash_drawer(
    cash_drawer_id: CashDrawerIdPath,
    body: CloseCashDrawerRequestSchema,
    principal: RequireBillingManageAtAnyScopeDep,
    use_case: CloseCashDrawerUseCaseDep,
) -> ApiResponse[CashDrawerResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        CloseCashDrawerRequestDTO(
            cash_drawer_id=cash_drawer_id, closing_counted_amount=body.closing_counted_amount
        ),
    )
    return ApiResponse(data=_cash_drawer_to_schema(result))
