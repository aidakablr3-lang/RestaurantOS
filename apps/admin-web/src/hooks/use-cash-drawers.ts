import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { closeCashDrawer, getOpenCashDrawer, openCashDrawer } from "@/lib/api/cash-drawers"
import type { CloseCashDrawerRequest, OpenCashDrawerRequest } from "@/types/cash-drawer"

export const cashDrawerKeys = {
  all: ["cash-drawers"] as const,
  open: (branchId: string) => [...cashDrawerKeys.all, "open", branchId] as const,
}

export function useOpenCashDrawerLookup(branchId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: cashDrawerKeys.open(branchId),
    queryFn: () => getOpenCashDrawer(branchId),
    enabled: options?.enabled ?? true,
  })
}

export function useOpenCashDrawer(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: OpenCashDrawerRequest) => openCashDrawer(branchId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cashDrawerKeys.open(branchId) })
    },
  })
}

export function useCloseCashDrawer(branchId: string) {
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
      queryClient.invalidateQueries({ queryKey: cashDrawerKeys.open(branchId) })
    },
  })
}
