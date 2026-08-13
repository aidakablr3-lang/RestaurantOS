import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  addGuestOrderItem,
  createGuestOrder,
  getGuestMenu,
  getGuestOrder,
  submitGuestOrder,
} from "@/lib/api/guest-order"
import type { AddOrderItemRequest } from "@/types/order"

export const guestOrderKeys = {
  menu: (token: string) => ["guest-menu", token] as const,
  order: (token: string, orderId: string) => ["guest-order", token, orderId] as const,
}

export function useGuestMenu(token: string) {
  return useQuery({
    queryKey: guestOrderKeys.menu(token),
    queryFn: () => getGuestMenu(token),
    retry: false,
  })
}

// Polls kitchen/order status every 5s while the guest has the order-status
// screen open -- the only "live update" mechanism this feature has (no
// WebSocket/SSE infrastructure exists anywhere in this codebase to reuse).
export function useGuestOrder(
  token: string,
  orderId: string | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: guestOrderKeys.order(token, orderId ?? ""),
    queryFn: () => getGuestOrder(token, orderId as string),
    enabled: Boolean(orderId) && (options?.enabled ?? true),
    refetchInterval: 5_000,
    retry: false,
  })
}

export function useCreateGuestOrder(token: string) {
  return useMutation({
    mutationFn: () => createGuestOrder(token),
  })
}

export function useAddGuestOrderItem(token: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orderId, body }: { orderId: string; body: AddOrderItemRequest }) =>
      addGuestOrderItem(token, orderId, body),
    onSuccess: (order) => {
      queryClient.setQueryData(guestOrderKeys.order(token, order.id), order)
    },
  })
}

export function useSubmitGuestOrder(token: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (orderId: string) => submitGuestOrder(token, orderId),
    onSuccess: (order) => {
      queryClient.setQueryData(guestOrderKeys.order(token, order.id), order)
    },
  })
}
