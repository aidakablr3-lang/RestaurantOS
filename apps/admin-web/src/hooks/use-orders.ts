import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { addOrderItem, closeOrder, createOrder, fireOrder, getOrder, listOrders, voidOrder } from "@/lib/api/orders"
import type { AddOrderItemRequest, CreateOrderRequest, ListOrdersParams } from "@/types/order"

export const orderKeys = {
  all: ["orders"] as const,
  lists: (branchId: string) => [...orderKeys.all, "list", branchId] as const,
  list: (branchId: string, params: ListOrdersParams) => [...orderKeys.lists(branchId), params] as const,
  details: (branchId: string) => [...orderKeys.all, "detail", branchId] as const,
  detail: (branchId: string, orderId: string) => [...orderKeys.details(branchId), orderId] as const,
}

export function useOrders(
  branchId: string,
  params: ListOrdersParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: orderKeys.list(branchId, params),
    queryFn: () => listOrders(branchId, params),
    enabled: options?.enabled,
  })
}

export function useOrder(
  branchId: string,
  orderId: string | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: orderKeys.detail(branchId, orderId ?? ""),
    queryFn: () => getOrder(branchId, orderId as string),
    enabled: Boolean(orderId) && (options?.enabled ?? true),
  })
}

function invalidateOrder(
  queryClient: ReturnType<typeof useQueryClient>,
  branchId: string,
  orderId: string
) {
  queryClient.invalidateQueries({ queryKey: orderKeys.detail(branchId, orderId) })
  queryClient.invalidateQueries({ queryKey: orderKeys.lists(branchId) })
}

export function useCreateOrder(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateOrderRequest
      idempotencyKey: string
    }) => createOrder(branchId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: orderKeys.lists(branchId) })
    },
  })
}

export function useAddOrderItem(branchId: string, orderId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: AddOrderItemRequest
      idempotencyKey: string
    }) => addOrderItem(orderId, body, idempotencyKey),
    onSuccess: () => invalidateOrder(queryClient, branchId, orderId),
  })
}

export function useFireOrder(branchId: string, orderId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (idempotencyKey: string) => fireOrder(orderId, idempotencyKey),
    onSuccess: () => invalidateOrder(queryClient, branchId, orderId),
  })
}

export function useCloseOrder(branchId: string, orderId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (idempotencyKey: string) => closeOrder(orderId, idempotencyKey),
    onSuccess: () => invalidateOrder(queryClient, branchId, orderId),
  })
}

export function useVoidOrder(branchId: string, orderId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (idempotencyKey: string) => voidOrder(orderId, idempotencyKey),
    onSuccess: () => invalidateOrder(queryClient, branchId, orderId),
  })
}
