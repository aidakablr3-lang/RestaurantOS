/**
 * Mirrors modules/operations/presentation/api/v1/cash_drawer_router.py's
 * CashDrawerResponseSchema / Open·Close RequestSchemas and the domain's
 * CashDrawerStatus StrEnum. Field names are camelCase on the wire; money
 * fields are decimal strings. ``expectedCashAmount``/``varianceAmount``
 * are computed at read time, only populated once the drawer is closed.
 */

export type CashDrawerStatus = "open" | "closed"

export interface CashDrawer {
  id: string
  tenantId: string
  branchId: string
  status: CashDrawerStatus
  openingFloatAmount: string
  openedAt: string
  createdAt: string
  terminalId: string | null
  closingCountedAmount: string | null
  closedAt: string | null
  expectedCashAmount: string | null
  varianceAmount: string | null
}

export interface OpenCashDrawerRequest {
  openingFloatAmount: string
  terminalId?: string | null
}

export interface CloseCashDrawerRequest {
  closingCountedAmount: string
}
