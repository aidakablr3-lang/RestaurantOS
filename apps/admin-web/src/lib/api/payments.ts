import { apiClient } from "@/lib/api-client"
import type { Payment, RecordPaymentRequest, Refund, RequestRefundRequest } from "@/types/payment"

export function recordPayment(billId: string, body: RecordPaymentRequest) {
  return apiClient.post<Payment>(`/api/v1/bills/${billId}/payments`, body)
}

export function listPayments(billId: string) {
  return apiClient.get<Payment[]>(`/api/v1/bills/${billId}/payments`)
}

export function requestRefund(paymentId: string, body: RequestRefundRequest) {
  return apiClient.post<Refund>(`/api/v1/payments/${paymentId}/refund`, body)
}
