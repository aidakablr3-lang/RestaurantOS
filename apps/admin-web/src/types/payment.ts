/**
 * Mirrors modules/operations/presentation/api/v1/payment_router.py's
 * PaymentResponseSchema / RecordPaymentRequestSchema and the domain's
 * TenderType / PaymentStatus StrEnums. Field names are camelCase on the
 * wire; money fields are decimal strings.
 *
 * There is no tip field on RecordPaymentRequest -- a tip is not part of
 * the restaurant bill (P0 correction, 2026-08-12); the customer pays
 * exactly the bill's amountDue. `Payment.tipAmount` is still reported
 * on the response (always "0.0000" for any payment recorded after this
 * correction) purely for backward compatibility with historical rows.
 *
 * RestaurantOS v1 has no refund workflow -- see docs/AI_HANDOFF.md.
 * A failed/disputed transaction is handled entirely by the payment
 * provider/bank, outside RestaurantOS.
 */

export type TenderType = "cash" | "card" | "wallet"

export type PaymentStatus = "authorized" | "captured" | "settled" | "declined"

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
  gatewayTokenRef?: string | null
  gatewayLast4?: string | null
}
