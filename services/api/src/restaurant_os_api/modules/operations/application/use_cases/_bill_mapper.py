from __future__ import annotations

from decimal import Decimal

from restaurant_os_api.modules.operations.application.dto import (
    BillAdjustmentDTO,
    BillDTO,
    OrderTaxLineDTO,
)
from restaurant_os_api.modules.operations.domain.entities import (
    Bill,
    BillAdjustment,
    OrderTaxLine,
)


def order_tax_line_to_dto(tax_line: OrderTaxLine) -> OrderTaxLineDTO:
    return OrderTaxLineDTO(
        id=tax_line.id,
        order_id=tax_line.order_id,
        tax_id=tax_line.tax_id,
        taxable_amount=tax_line.taxable_amount,
        tax_rate_snapshot=tax_line.tax_rate_snapshot,
        tax_amount=tax_line.tax_amount,
        created_at=tax_line.created_at,
    )


def bill_adjustment_to_dto(adjustment: BillAdjustment) -> BillAdjustmentDTO:
    return BillAdjustmentDTO(
        id=adjustment.id,
        bill_id=adjustment.bill_id,
        adjustment_type=adjustment.adjustment_type.value,
        amount=adjustment.amount,
        created_at=adjustment.created_at,
        reference_type=adjustment.reference_type,
        reference_id=adjustment.reference_id,
        reason=adjustment.reason,
        approved_by_user_id=adjustment.approved_by_user_id,
    )


def bill_to_dto(
    bill: Bill,
    *,
    subtotal_amount: Decimal,
    tax_amount: Decimal,
    tax_lines: list[OrderTaxLine],
    adjustments: list[BillAdjustment],
    amount_paid: Decimal,
) -> BillDTO:
    adjustments_total = sum((a.amount for a in adjustments), Decimal(0))
    amount_due = subtotal_amount + tax_amount + adjustments_total - amount_paid
    return BillDTO(
        id=bill.id,
        tenant_id=bill.tenant_id,
        branch_id=bill.branch_id,
        status=bill.status.value,
        created_at=bill.created_at,
        order_id=bill.order_id,
        tab_id=bill.tab_id,
        subtotal_amount=subtotal_amount,
        tax_amount=tax_amount,
        adjustments_total=adjustments_total,
        amount_due=amount_due,
        amount_paid=amount_paid,
        tax_lines=[order_tax_line_to_dto(t) for t in tax_lines],
        adjustments=[bill_adjustment_to_dto(a) for a in adjustments],
    )
