import { guestApiClient } from "@/lib/guest-api-client"
import type { AddOrderItemRequest, Order } from "@/types/order"
import type { GuestMenu } from "@/types/guest-order"

const QR_BASE = (token: string) => `/api/v1/qr/${encodeURIComponent(token)}`

export function getGuestMenu(token: string) {
  return guestApiClient.get<GuestMenu>(`${QR_BASE(token)}/menu`)
}

export function createGuestOrder(token: string) {
  return guestApiClient.post<Order>(`${QR_BASE(token)}/orders`)
}

export function addGuestOrderItem(token: string, orderId: string, body: AddOrderItemRequest) {
  return guestApiClient.post<Order>(`${QR_BASE(token)}/orders/${orderId}/items`, body)
}

export function submitGuestOrder(token: string, orderId: string) {
  return guestApiClient.post<Order>(`${QR_BASE(token)}/orders/${orderId}/submit`)
}

export function getGuestOrder(token: string, orderId: string) {
  return guestApiClient.get<Order>(`${QR_BASE(token)}/orders/${orderId}`)
}
