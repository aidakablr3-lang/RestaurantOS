/**
 * Mirrors modules/operations/presentation/api/v1/payment_router.py's
 * PaymentResponseSchema / RefundResponseSchema / RecordPaymentRequestSchema
 * / RequestRefundRequestSchema and the domain's TenderType / PaymentStatus
 * / RefundStatus StrEnums. Field names are camelCase on the wire; money
 * fields are decimal strings.
 */

export type TenderType = "cash" | "card" | "wallet"

export type PaymentStatus = "authorized" | "captured" | "settled" | "declined"

export type RefundStatus = "requested" | "approved" | "processed"

export interface Payment {
  id: string
  tenantId: string
  branchId: string
  billId: string
  tenderType: TenderType
  amount: string
  currencyCode: string
  tipAmount: string
  status: PaymentStatus
  createdAt: string
  gatewayTokenRef: string | null
  gatewayLast4: string | null
}

export interface RecordPaymentRequest {
  tenderType: TenderType
  amount: string
  tipAmount?: string
  gatewayTokenRef?: string | null
  gatewayLast4?: string | null
}

export interface Refund {
  id: string
  tenantId: string
  branchId: string
  paymentId: string
  orderId: string
  approvedByUserId: string
  amount: string
  status: RefundStatus
  createdAt: string
}

export interface RequestRefundRequest {
  approvedByUserId: string
  amount: string
}
