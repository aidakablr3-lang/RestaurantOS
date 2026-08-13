from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import PaymentDTO, RefundDTO
from restaurant_os_api.modules.operations.domain.entities import Payment, Refund


def payment_to_dto(payment: Payment) -> PaymentDTO:
    return PaymentDTO(
        id=payment.id,
        tenant_id=payment.tenant_id,
        branch_id=payment.branch_id,
        bill_id=payment.bill_id,
        tender_type=payment.tender_type.value,
        amount=payment.amount,
        currency_code=payment.currency_code,
        tip_amount=payment.tip_amount,
        status=payment.status.value,
        created_at=payment.created_at,
        gateway_token_ref=payment.gateway_token_ref,
        gateway_last4=payment.gateway_last4,
    )


def refund_to_dto(refund: Refund) -> RefundDTO:
    return RefundDTO(
        id=refund.id,
        tenant_id=refund.tenant_id,
        branch_id=refund.branch_id,
        payment_id=refund.payment_id,
        order_id=refund.order_id,
        approved_by_user_id=refund.approved_by_user_id,
        amount=refund.amount,
        status=refund.status.value,
        created_at=refund.created_at,
    )
