import { useQuery } from "@tanstack/react-query"

import { getEndOfDayReport } from "@/lib/api/reports"

export const reportKeys = {
  endOfDay: (branchId: string, date: string) => ["reports", "end-of-day", branchId, date] as const,
}

export function useEndOfDayReport(
  branchId: string,
  date: string,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: reportKeys.endOfDay(branchId, date),
    queryFn: () => getEndOfDayReport(branchId, date),
    enabled: Boolean(branchId) && Boolean(date) && (options?.enabled ?? true),
  })
}
