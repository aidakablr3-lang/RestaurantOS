import { apiClient } from "@/lib/api-client"
import type { Payment, RecordPaymentRequest } from "@/types/payment"

export function recordPayment(billId: string, body: RecordPaymentRequest) {
  return apiClient.post<Payment>(`/api/v1/bills/${billId}/payments`, body)
}

export function listPayments(billId: string) {
  return apiClient.get<Payment[]>(`/api/v1/bills/${billId}/payments`)
}
