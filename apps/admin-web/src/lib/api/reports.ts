import { apiClient } from "@/lib/api-client"
import type { EndOfDayReport } from "@/types/report"

export function getEndOfDayReport(branchId: string, date: string) {
  const search = new URLSearchParams({ date })
  return apiClient.get<EndOfDayReport>(
    `/api/v1/branches/${branchId}/reports/end-of-day?${search.toString()}`
  )
}
