import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { createDiscount, listDiscounts } from "@/lib/api/discounts"
import type { CreateDiscountRequest, ListDiscountsParams } from "@/types/discount"

export const discountKeys = {
  all: ["discounts"] as const,
  lists: () => [...discountKeys.all, "list"] as const,
  list: (params: ListDiscountsParams) => [...discountKeys.lists(), params] as const,
}

export function useDiscounts(params: ListDiscountsParams, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: discountKeys.list(params),
    queryFn: () => listDiscounts(params),
    enabled: options?.enabled,
  })
}

export function useCreateDiscount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateDiscountRequest) => createDiscount(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: discountKeys.lists() })
    },
  })
}
