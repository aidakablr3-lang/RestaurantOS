/**
 * Mirrors modules/operations/presentation/schemas/report_schemas.py's
 * EndOfDayReportResponseSchema/TenderBreakdownResponseSchema/
 * TopMenuItemResponseSchema. Money fields are decimal strings, matching
 * every other module.
 */

export interface TenderBreakdown {
  tenderType: string
  amount: string
  paymentCount: number
}

export interface TopMenuItem {
  menuItemId: string
  name: string
  quantitySold: number
}

export interface EndOfDayReport {
  branchId: string
  reportDate: string
  currencyCode: string
  orderCount: number
  voidedOrderCount: number
  itemsSoldCount: number
  grossSalesAmount: string
  voidedSalesAmount: string
  outstandingAmount: string
  totalCollectedAmount: string
  totalTipsAmount: string
  totalRefundedAmount: string
  netCollectedAmount: string
  tenderBreakdown: TenderBreakdown[]
  topItems: TopMenuItem[]
}
