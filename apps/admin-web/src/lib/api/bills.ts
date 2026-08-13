import { apiClient } from "@/lib/api-client"
import type { ApplyBillAdjustmentRequest, Bill, CreateTaxRequest, Tax } from "@/types/bill"

export function createTax(body: CreateTaxRequest) {
  return apiClient.post<Tax>("/api/v1/taxes", body)
}

export function listTaxes() {
  return apiClient.get<Tax[]>("/api/v1/taxes")
}

export function generateBill(orderId: string) {
  return apiClient.post<Bill>(`/api/v1/orders/${orderId}/bill`, undefined)
}

export function getBill(billId: string) {
  return apiClient.get<Bill>(`/api/v1/bills/${billId}`)
}

export function applyBillAdjustment(billId: string, body: ApplyBillAdjustmentRequest) {
  return apiClient.post<Bill>(`/api/v1/bills/${billId}/adjustments`, body)
}
