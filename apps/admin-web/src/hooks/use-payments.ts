import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { listPayments, recordPayment } from "@/lib/api/payments"
import { billKeys } from "@/hooks/use-bills"
import type { RecordPaymentRequest } from "@/types/payment"

export const paymentKeys = {
  all: ["payments"] as const,
  lists: (billId: string) => [...paymentKeys.all, "list", billId] as const,
}

export function usePayments(billId: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: paymentKeys.lists(billId ?? ""),
    queryFn: () => listPayments(billId as string),
    enabled: Boolean(billId) && (options?.enabled ?? true),
  })
}

export function useRecordPayment(billId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: RecordPaymentRequest) => recordPayment(billId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paymentKeys.lists(billId) })
      queryClient.invalidateQueries({ queryKey: billKeys.detail(billId) })
    },
  })
}
