"""Application-layer DTOs for the End-of-Day report (full-day
operational simulation gap fix -- no reporting feature existed
anywhere in the codebase before this).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TenderBreakdownDTO:
    tender_type: str
    amount: Decimal
    payment_count: int


@dataclass(frozen=True, slots=True)
class TopMenuItemDTO:
    menu_item_id: str
    name: str
    quantity_sold: int


@dataclass(frozen=True, slots=True)
class EndOfDayReportDTO:
    branch_id: str
    report_date: str
    currency_code: str
    order_count: int
    voided_order_count: int
    items_sold_count: int
    gross_sales_amount: Decimal
    voided_sales_amount: Decimal
    outstanding_amount: Decimal
    total_collected_amount: Decimal
    total_tips_amount: Decimal
    total_refunded_amount: Decimal
    net_collected_amount: Decimal
    tender_breakdown: list[TenderBreakdownDTO] = field(default_factory=list)
    top_items: list[TopMenuItemDTO] = field(default_factory=list)
