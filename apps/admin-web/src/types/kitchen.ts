/**
 * Mirrors modules/operations/presentation/api/v1/kitchen_router.py's
 * KitchenTicketResponseSchema / KitchenItemResponseSchema /
 * Change·StatusRequestSchema and the domain's KitchenTicketStatus /
 * KitchenItemStatus StrEnums. Field names are camelCase on the wire.
 */

export type KitchenTicketStatus = "fired" | "in_progress" | "ready" | "served"

export type KitchenItemStatus = "queued" | "in_progress" | "ready" | "served"

export interface KitchenItem {
  id: string
  kitchenTicketId: string
  orderItemId: string
  status: KitchenItemStatus
  createdAt: string
}

export interface KitchenTicket {
  id: string
  tenantId: string
  orderId: string
  station: string
  status: KitchenTicketStatus
  createdAt: string
  items: KitchenItem[]
}

export interface ChangeKitchenTicketStatusRequest {
  status: KitchenTicketStatus
}

export interface ChangeKitchenItemStatusRequest {
  status: KitchenItemStatus
}

export interface ListKitchenTicketsParams {
  offset?: number
  limit?: number
}
