import { useMutation, useQueryClient } from "@tanstack/react-query"

import { closeCashDrawer, openCashDrawer } from "@/lib/api/cash-drawers"
import type { CloseCashDrawerRequest, OpenCashDrawerRequest } from "@/types/cash-drawer"

// No list/read endpoint exists on the backend for cash drawers -- a
// caller is expected to hold onto the CashDrawer returned by open()
// until it closes it. Both mutations exist purely to invalidate order/
// bill data that a drawer session's reconciliation figures might touch
// (settled cash payments), matching how CloseCashDrawerUseCase itself
// computes expectedCashAmount from real Payment rows.
export function useOpenCashDrawer(branchId: string) {
  return useMutation({
    mutationFn: (body: OpenCashDrawerRequest) => openCashDrawer(branchId, body),
  })
}

export function useCloseCashDrawer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      cashDrawerId,
      body,
    }: {
      cashDrawerId: string
      body: CloseCashDrawerRequest
    }) => closeCashDrawer(cashDrawerId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["payments"] })
    },
  })
}
