import { apiClient } from "@/lib/api-client"
import type {
  ChangeKitchenItemStatusRequest,
  ChangeKitchenTicketStatusRequest,
  KitchenItem,
  KitchenTicket,
  ListKitchenTicketsParams,
} from "@/types/kitchen"

export function listKitchenTickets(branchId: string, params: ListKitchenTicketsParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<KitchenTicket[]>(
    `/api/v1/branches/${branchId}/kitchen-tickets?${search.toString()}`
  )
}

export function changeKitchenTicketStatus(
  kitchenTicketId: string,
  body: ChangeKitchenTicketStatusRequest,
  idempotencyKey: string
) {
  return apiClient.post<KitchenTicket>(`/api/v1/kitchen-tickets/${kitchenTicketId}/status`, body, {
    idempotencyKey,
  })
}

export function changeKitchenItemStatus(
  kitchenItemId: string,
  body: ChangeKitchenItemStatusRequest,
  idempotencyKey: string
) {
  return apiClient.post<KitchenItem>(`/api/v1/kitchen-items/${kitchenItemId}/status`, body, {
    idempotencyKey,
  })
}
