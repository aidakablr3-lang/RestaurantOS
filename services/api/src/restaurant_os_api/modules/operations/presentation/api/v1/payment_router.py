"""Payment + Refund endpoints (Sprint 7 Step 4).

``refund`` is gated by its own, separate ``billing.refund`` permission
-- Architecture doc SS10's own explicit split from ``billing.manage``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, status

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.operations.application.dto import (
    PaymentDTO,
    RecordPaymentRequestDTO,
    RefundDTO,
    RequestRefundRequestDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    ListPaymentsUseCaseDep,
    RecordPaymentUseCaseDep,
    RequestRefundUseCaseDep,
    RequireBillingManageAtAnyScopeDep,
    RequireBillingReadAtAnyScopeDep,
    RequireBillingRefundAtAnyScopeDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.payment_schemas import (
    PaymentResponseSchema,
    RecordPaymentRequestSchema,
    RefundResponseSchema,
    RequestRefundRequestSchema,
)

router = APIRouter(tags=["payments"])

BillIdPath = Annotated[str, Path(min_length=26, max_length=26)]
PaymentIdPath = Annotated[str, Path(min_length=26, max_length=26)]


def _payment_to_schema(dto: PaymentDTO) -> PaymentResponseSchema:
    return PaymentResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        bill_id=dto.bill_id,
        tender_type=dto.tender_type,
        amount=dto.amount,
        currency_code=dto.currency_code,
        tip_amount=dto.tip_amount,
        status=dto.status,
        created_at=dto.created_at,
        gateway_token_ref=dto.gateway_token_ref,
        gateway_last4=dto.gateway_last4,
    )


def _refund_to_schema(dto: RefundDTO) -> RefundResponseSchema:
    return RefundResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        payment_id=dto.payment_id,
        order_id=dto.order_id,
        approved_by_user_id=dto.approved_by_user_id,
        amount=dto.amount,
        status=dto.status,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/bills/{bill_id}/payments",
    response_model=ApiResponse[PaymentResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def record_payment(
    bill_id: BillIdPath,
    body: RecordPaymentRequestSchema,
    principal: RequireBillingManageAtAnyScopeDep,
    use_case: RecordPaymentUseCaseDep,
) -> ApiResponse[PaymentResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        RecordPaymentRequestDTO(
            bill_id=bill_id,
            tender_type=body.tender_type.value,
            amount=body.amount,
            tip_amount=body.tip_amount,
            gateway_token_ref=body.gateway_token_ref,
            gateway_last4=body.gateway_last4,
        ),
    )
    return ApiResponse(data=_payment_to_schema(result))


@router.get(
    "/api/v1/bills/{bill_id}/payments",
    response_model=ApiResponse[list[PaymentResponseSchema]],
)
async def list_payments(
    bill_id: BillIdPath,
    principal: RequireBillingReadAtAnyScopeDep,
    use_case: ListPaymentsUseCaseDep,
) -> ApiResponse[list[PaymentResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, principal.user_id, bill_id)
    return ApiResponse(data=[_payment_to_schema(p) for p in result])


@router.post(
    "/api/v1/payments/{payment_id}/refund",
    response_model=ApiResponse[RefundResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def request_refund(
    payment_id: PaymentIdPath,
    body: RequestRefundRequestSchema,
    principal: RequireBillingRefundAtAnyScopeDep,
    use_case: RequestRefundUseCaseDep,
) -> ApiResponse[RefundResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        RequestRefundRequestDTO(
            payment_id=payment_id,
            approved_by_user_id=body.approved_by_user_id,
            amount=body.amount,
        ),
    )
    return ApiResponse(data=_refund_to_schema(result))
