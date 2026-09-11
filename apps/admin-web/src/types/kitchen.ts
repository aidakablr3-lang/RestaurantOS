/**
 * Mirrors modules/operations/presentation/api/v1/kitchen_router.py's
 * KitchenTicketResponseSchema / KitchenItemResponseSchema /
 * Change·StatusRequestSchema and the domain's KitchenTicketStatus /
 * KitchenItemStatus StrEnums. Field names are camelCase on the wire.
 */

export type KitchenTicketStatus = "fired" | "in_progress" | "ready" | "served" | "cancelled"

export type KitchenItemStatus = "queued" | "in_progress" | "ready" | "served" | "cancelled"

export interface KitchenItem {
  id: string
  kitchenTicketId: string
  orderItemId: string
  menuItemName: string
  quantity: number
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
  // Set only once the ticket is cancelled (VoidOrderUseCase's kitchen
  // cascade) -- the KDS uses this to decide how long a cancelled
  // ticket stays visible before dropping off the board. See
  // kitchen/page.tsx's own CANCELLED_VISIBILITY_MS.
  cancelledAt: string | null
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
