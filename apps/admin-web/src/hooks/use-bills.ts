import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { applyBillAdjustment, createTax, generateBill, getBill, listTaxes } from "@/lib/api/bills"
import type { ApplyBillAdjustmentRequest } from "@/types/bill"

export const billKeys = {
  all: ["bills"] as const,
  details: () => [...billKeys.all, "detail"] as const,
  detail: (billId: string) => [...billKeys.details(), billId] as const,
}

export const taxKeys = {
  all: ["taxes"] as const,
  lists: () => [...taxKeys.all, "list"] as const,
}

export function useTaxes(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: taxKeys.lists(),
    queryFn: () => listTaxes(),
    enabled: options?.enabled ?? true,
  })
}

export function useBill(billId: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: billKeys.detail(billId ?? ""),
    queryFn: () => getBill(billId as string),
    enabled: Boolean(billId) && (options?.enabled ?? true),
  })
}

export function useGenerateBill() {
  return useMutation({
    mutationFn: (orderId: string) => generateBill(orderId),
  })
}

export function useApplyBillAdjustment(billId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ApplyBillAdjustmentRequest) => applyBillAdjustment(billId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: billKeys.detail(billId) })
    },
  })
}

export function useCreateTax() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createTax,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: taxKeys.lists() })
    },
  })
}
