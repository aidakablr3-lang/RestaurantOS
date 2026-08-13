import { apiClient } from "@/lib/api-client"
import type { AddOrderItemRequest, CreateOrderRequest, ListOrdersParams, Order } from "@/types/order"

const BRANCH_BASE = (branchId: string) => `/api/v1/branches/${branchId}/orders`

export function listOrders(branchId: string, params: ListOrdersParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  if (params.tableId) search.set("tableId", params.tableId)
  if (params.status) search.set("status", params.status)
  return apiClient.get<Order[]>(`${BRANCH_BASE(branchId)}?${search.toString()}`)
}

export function getOrder(branchId: string, orderId: string) {
  return apiClient.get<Order>(`${BRANCH_BASE(branchId)}/${orderId}`)
}

export function createOrder(branchId: string, body: CreateOrderRequest, idempotencyKey: string) {
  return apiClient.post<Order>(BRANCH_BASE(branchId), body, { idempotencyKey })
}

export function addOrderItem(orderId: string, body: AddOrderItemRequest, idempotencyKey: string) {
  return apiClient.post<Order>(`/api/v1/orders/${orderId}/items`, body, { idempotencyKey })
}

export function fireOrder(orderId: string, idempotencyKey: string) {
  return apiClient.post<Order>(`/api/v1/orders/${orderId}/fire`, undefined, { idempotencyKey })
}

export function closeOrder(orderId: string, idempotencyKey: string) {
  return apiClient.post<Order>(`/api/v1/orders/${orderId}/close`, undefined, { idempotencyKey })
}

export function voidOrder(orderId: string, idempotencyKey: string) {
  return apiClient.post<Order>(`/api/v1/orders/${orderId}/void`, undefined, { idempotencyKey })
}

export function voidOrderItem(orderId: string, orderItemId: string, idempotencyKey: string) {
  return apiClient.post<Order>(`/api/v1/orders/${orderId}/items/${orderItemId}/void`, undefined, {
    idempotencyKey,
  })
}
