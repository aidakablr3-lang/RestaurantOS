"""End-of-Day report route (full-day operational simulation gap fix --
the first reporting/analytics feature in this codebase).

Branch-nested, gated directly by ``require_branch_permission
("reports.read")`` -- ``branch_id`` is already in the URL, so this
mirrors ``GET /api/v1/branches/{branch_id}/orders``'s own simple
"coarse gate is the only gate" shape rather than the flat-route
"coarse gate + fine-grained use-case resolve" split (see
``GetEndOfDayReportUseCase``'s own docstring for why no internal
re-check is needed).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.operations.presentation.dependencies import (
    GetEndOfDayReportUseCaseDep,
    RequireReportsReadDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.report_schemas import (
    EndOfDayReportResponseSchema,
    TenderBreakdownResponseSchema,
    TopMenuItemResponseSchema,
)

router = APIRouter(tags=["reports"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]


@router.get(
    "/api/v1/branches/{branch_id}/reports/end-of-day",
    response_model=ApiResponse[EndOfDayReportResponseSchema],
)
async def get_end_of_day_report(
    branch_id: BranchIdPath,
    principal: RequireReportsReadDep,
    use_case: GetEndOfDayReportUseCaseDep,
    report_date: Annotated[date, Query(alias="date")],
) -> ApiResponse[EndOfDayReportResponseSchema]:
    result = await use_case.execute(principal.tenant_id, branch_id, report_date)
    body = EndOfDayReportResponseSchema(
        branch_id=result.branch_id,
        report_date=result.report_date,
        currency_code=result.currency_code,
        order_count=result.order_count,
        voided_order_count=result.voided_order_count,
        items_sold_count=result.items_sold_count,
        gross_sales_amount=result.gross_sales_amount,
        voided_sales_amount=result.voided_sales_amount,
        outstanding_amount=result.outstanding_amount,
        total_collected_amount=result.total_collected_amount,
        total_tips_amount=result.total_tips_amount,
        total_refunded_amount=result.total_refunded_amount,
        net_collected_amount=result.net_collected_amount,
        tender_breakdown=[
            TenderBreakdownResponseSchema(
                tender_type=t.tender_type, amount=t.amount, payment_count=t.payment_count
            )
            for t in result.tender_breakdown
        ],
        top_items=[
            TopMenuItemResponseSchema(
                menu_item_id=i.menu_item_id, name=i.name, quantity_sold=i.quantity_sold
            )
            for i in result.top_items
        ],
    )
    return ApiResponse(data=body)
