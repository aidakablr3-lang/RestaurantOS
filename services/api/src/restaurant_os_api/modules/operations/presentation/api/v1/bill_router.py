"""Tax + Bill + BillAdjustment endpoints (Sprint 7 Step 4).

``POST /api/v1/taxes`` is tenant-wide, flat, gated
``require_permission("billing.manage")`` -- the same tenant-wide shape
``ModifierGroupRouter`` uses. ``bill``/``adjustments`` are flat, order-
or bill-scoped, gated the same coarse/fine split as every other flat
Operations route.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.operations.application.dto import (
    ApplyBillAdjustmentRequestDTO,
    BillDTO,
    GenerateBillRequestDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    ApplyBillAdjustmentUseCaseDep,
    CreateTaxUseCaseDep,
    GenerateBillUseCaseDep,
    GetBillUseCaseDep,
    RequireBillingManageAtAnyScopeDep,
    RequireBillingManageTenantWideDep,
    RequireBillingReadAtAnyScopeDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.bill_schemas import (
    ApplyBillAdjustmentRequestSchema,
    BillAdjustmentResponseSchema,
    BillResponseSchema,
    CreateTaxRequestSchema,
    OrderTaxLineResponseSchema,
    TaxResponseSchema,
)

router = APIRouter(tags=["billing"])

OrderIdPath = Annotated[str, Path(min_length=26, max_length=26)]
BillIdPath = Annotated[str, Path(min_length=26, max_length=26)]


def _bill_to_schema(dto: BillDTO) -> BillResponseSchema:
    return BillResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        status=dto.status,
        created_at=dto.created_at,
        order_id=dto.order_id,
        tab_id=dto.tab_id,
        subtotal_amount=dto.subtotal_amount,
        tax_amount=dto.tax_amount,
        adjustments_total=dto.adjustments_total,
        amount_due=dto.amount_due,
        amount_paid=dto.amount_paid,
        tax_lines=[
            OrderTaxLineResponseSchema(
                id=t.id,
                order_id=t.order_id,
                tax_id=t.tax_id,
                taxable_amount=t.taxable_amount,
                tax_rate_snapshot=t.tax_rate_snapshot,
                tax_amount=t.tax_amount,
                created_at=t.created_at,
            )
            for t in dto.tax_lines
        ],
        adjustments=[
            BillAdjustmentResponseSchema(
                id=a.id,
                bill_id=a.bill_id,
                adjustment_type=a.adjustment_type,
                amount=a.amount,
                created_at=a.created_at,
                reference_type=a.reference_type,
                reference_id=a.reference_id,
                reason=a.reason,
                approved_by_user_id=a.approved_by_user_id,
            )
            for a in dto.adjustments
        ],
    )


@router.post(
    "/api/v1/taxes",
    response_model=ApiResponse[TaxResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_tax(
    body: CreateTaxRequestSchema,
    principal: RequireBillingManageTenantWideDep,
    use_case: CreateTaxUseCaseDep,
) -> ApiResponse[TaxResponseSchema]:
    tax = await use_case.execute(principal.tenant_id, body.name, str(body.rate))
    return ApiResponse(
        data=TaxResponseSchema(
            id=tax.id,
            tenant_id=tax.tenant_id,
            name=tax.name,
            rate=tax.rate,
            is_active=tax.is_active,
            created_at=tax.created_at,
        )
    )


@router.post(
    "/api/v1/orders/{order_id}/bill",
    response_model=ApiResponse[BillResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def generate_bill(
    order_id: OrderIdPath,
    principal: RequireBillingManageAtAnyScopeDep,
    use_case: GenerateBillUseCaseDep,
) -> ApiResponse[BillResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id, principal.user_id, GenerateBillRequestDTO(order_id=order_id)
    )
    return ApiResponse(data=_bill_to_schema(result))


@router.get("/api/v1/bills/{bill_id}", response_model=ApiResponse[BillResponseSchema])
async def get_bill(
    bill_id: BillIdPath,
    principal: RequireBillingReadAtAnyScopeDep,
    use_case: GetBillUseCaseDep,
) -> ApiResponse[BillResponseSchema]:
    result = await use_case.execute(principal.tenant_id, principal.user_id, bill_id)
    return ApiResponse(data=_bill_to_schema(result))


@router.post(
    "/api/v1/bills/{bill_id}/adjustments",
    response_model=ApiResponse[BillResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def apply_bill_adjustment(
    bill_id: BillIdPath,
    body: ApplyBillAdjustmentRequestSchema,
    principal: RequireBillingManageAtAnyScopeDep,
    use_case: ApplyBillAdjustmentUseCaseDep,
) -> JSONResponse:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        ApplyBillAdjustmentRequestDTO(
            bill_id=bill_id,
            adjustment_type=body.adjustment_type.value,
            amount=body.amount,
            discount_id=body.discount_id,
            reason=body.reason,
            approved_by_user_id=body.approved_by_user_id,
        ),
    )
    response: ApiResponse[BillResponseSchema] = ApiResponse(data=_bill_to_schema(result))
    body_dict: dict[str, Any] = response.model_dump(mode="json", by_alias=True)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=body_dict)
