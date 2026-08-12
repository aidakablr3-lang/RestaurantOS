import { apiClient } from "@/lib/api-client"
import type { CashDrawer, CloseCashDrawerRequest, OpenCashDrawerRequest } from "@/types/cash-drawer"

export function openCashDrawer(branchId: string, body: OpenCashDrawerRequest) {
  return apiClient.post<CashDrawer>(`/api/v1/branches/${branchId}/cash-drawers`, body)
}

export function closeCashDrawer(cashDrawerId: string, body: CloseCashDrawerRequest) {
  return apiClient.post<CashDrawer>(`/api/v1/cash-drawers/${cashDrawerId}/close`, body)
}
