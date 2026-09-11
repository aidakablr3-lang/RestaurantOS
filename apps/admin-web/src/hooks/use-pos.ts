import { useMutation, useQueryClient } from "@tanstack/react-query"

import { orderKeys } from "@/hooks/use-orders"
import { addOrderItem, fireOrder, updateOrderItemQuantity, voidOrderItem } from "@/lib/api/orders"
import { recordPayment } from "@/lib/api/payments"
import type { AddOrderItemRequest, UpdateOrderItemQuantityRequest } from "@/types/order"
import type { RecordPaymentRequest } from "@/types/payment"

// Flexible counterparts to the fixed-orderId hooks in use-orders.ts.
// Those are curried by orderId at hook-creation time, which fits every
// existing page (the order already exists, its id is a route param) but
// not the counter POS screen (`/branches/[branchId]/pos`) -- there, no
// order exists until the first tile tap, so orderId has to be a
// mutation-time argument instead of a closure. Same reasoning for
// recordPayment (billId doesn't exist until Pay generates a bill).

export function usePosAddOrderItem(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      orderId,
      body,
      idempotencyKey,
    }: {
      orderId: string
      body: AddOrderItemRequest
      idempotencyKey: string
    }) => addOrderItem(orderId, body, idempotencyKey),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: orderKeys.detail(branchId, variables.orderId) })
    },
  })
}

export function usePosUpdateOrderItemQuantity(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      orderId,
      orderItemId,
      body,
    }: {
      orderId: string
      orderItemId: string
      body: UpdateOrderItemQuantityRequest
    }) => updateOrderItemQuantity(orderId, orderItemId, body),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: orderKeys.detail(branchId, variables.orderId) })
    },
  })
}

export function usePosVoidOrderItem(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      orderId,
      orderItemId,
      idempotencyKey,
    }: {
      orderId: string
      orderItemId: string
      idempotencyKey: string
    }) => voidOrderItem(orderId, orderItemId, idempotencyKey),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: orderKeys.detail(branchId, variables.orderId) })
    },
  })
}

export function usePosFireOrder(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orderId, idempotencyKey }: { orderId: string; idempotencyKey: string }) =>
      fireOrder(orderId, idempotencyKey),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: orderKeys.detail(branchId, variables.orderId) })
    },
  })
}

export function usePosRecordPayment() {
  return useMutation({
    mutationFn: ({ billId, body }: { billId: string; body: RecordPaymentRequest }) =>
      recordPayment(billId, body),
  })
}
