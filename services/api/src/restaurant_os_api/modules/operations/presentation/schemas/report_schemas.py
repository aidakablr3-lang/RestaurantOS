"""Pydantic response schemas for the End-of-Day report."""

from __future__ import annotations

from decimal import Decimal

from restaurant_os_api.core.response import CamelModel


class TenderBreakdownResponseSchema(CamelModel):
    tender_type: str
    amount: Decimal
    payment_count: int


class TopMenuItemResponseSchema(CamelModel):
    menu_item_id: str
    name: str
    quantity_sold: int


class EndOfDayReportResponseSchema(CamelModel):
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
    tender_breakdown: list[TenderBreakdownResponseSchema]
    top_items: list[TopMenuItemResponseSchema]
