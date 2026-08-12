/**
 * Mirrors modules/operations/presentation/api/v1/bill_router.py's
 * TaxResponseSchema / BillResponseSchema / OrderTaxLineResponseSchema /
 * BillAdjustmentResponseSchema / Create·Apply RequestSchemas and the
 * domain's BillStatus / BillAdjustmentType StrEnums. Field names are
 * camelCase on the wire; money fields are decimal strings.
 */

export type BillStatus = "open" | "partially_paid" | "closed"

export type BillAdjustmentType = "discount" | "service_charge" | "tip" | "comp" | "write_off"

export interface Tax {
  id: string
  tenantId: string
  name: string
  rate: string
  isActive: boolean
  createdAt: string
}

export interface CreateTaxRequest {
  name: string
  rate: string
}

export interface OrderTaxLine {
  id: string
  orderId: string
  taxId: string
  taxableAmount: string
  taxRateSnapshot: string
  taxAmount: string
  createdAt: string
}

export interface BillAdjustment {
  id: string
  billId: string
  adjustmentType: BillAdjustmentType
  amount: string
  createdAt: string
  referenceType: string | null
  referenceId: string | null
  reason: string | null
  approvedByUserId: string | null
}

export interface Bill {
  id: string
  tenantId: string
  branchId: string
  status: BillStatus
  createdAt: string
  orderId: string | null
  tabId: string | null
  subtotalAmount: string
  taxAmount: string
  adjustmentsTotal: string
  amountDue: string
  amountPaid: string
  taxLines: OrderTaxLine[]
  adjustments: BillAdjustment[]
}

export interface ApplyBillAdjustmentRequest {
  adjustmentType: BillAdjustmentType
  amount?: string | null
  discountId?: string | null
  reason?: string | null
  approvedByUserId?: string | null
}
