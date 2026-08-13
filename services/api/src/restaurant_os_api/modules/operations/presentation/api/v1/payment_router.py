"""Payment endpoints (Sprint 7 Step 4).

**Refund retired from the active product surface (P0 correction,
2026-08-12).** RestaurantOS v1 is responsible for recording what a
customer consumed, calculating the bill, recording settlement, and
closing out the order/table -- not for acting as a payment-provider
dispute/refund system. A failed, reversed, or disputed transaction is
handled entirely through the relevant payment provider/bank, outside
RestaurantOS. The ``POST /api/v1/payments/{id}/refund`` route that
used to exist here has been removed. The underlying ``Refund`` domain
entity, ``RequestRefundUseCase``, repository methods, and reversing
ledger logic are all still present and unit-tested (preserving the
abstraction for a future real payment-gateway integration) -- they are
simply no longer wired to any HTTP route. See ``docs/AI_HANDOFF.md``
for the full record of this decision.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, status

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.operations.application.dto import (
    PaymentDTO,
    RecordPaymentRequestDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    ListPaymentsUseCaseDep,
    RecordPaymentUseCaseDep,
    RequireBillingManageAtAnyScopeDep,
    RequireBillingReadAtAnyScopeDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.payment_schemas import (
    PaymentResponseSchema,
    RecordPaymentRequestSchema,
)

router = APIRouter(tags=["payments"])

BillIdPath = Annotated[str, Path(min_length=26, max_length=26)]


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
