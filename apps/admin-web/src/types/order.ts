/**
 * Mirrors modules/operations/presentation/api/v1/order_router.py's
 * OrderResponseSchema / OrderItemResponseSchema / CreateOrderRequestSchema /
 * AddOrderItemRequestSchema and the domain's OrderSource / OrderStatus /
 * OrderItemLineStatus StrEnums. Field names are camelCase on the wire;
 * money fields are decimal strings, matching every other module.
 */

export type OrderSource = "pos" | "qr" | "delivery" | "takeaway"

export type OrderStatus = "open" | "fired" | "served" | "billed" | "closed" | "voided"

export type OrderItemLineStatus = "added" | "fired" | "ready" | "served" | "voided"

export interface OrderItem {
  id: string
  orderId: string
  menuItemId: string
  quantity: number
  unitPriceAmount: string
  lineStatus: OrderItemLineStatus
  createdAt: string
  modifiersSnapshot: Record<string, unknown>[]
  recipeCostSnapshot: string | null
}

export interface Order {
  id: string
  tenantId: string
  branchId: string
  orderSource: OrderSource
  status: OrderStatus
  subtotalAmount: string
  taxAmount: string
  totalAmount: string
  currencyCode: string
  openedAt: string
  createdAt: string
  items: OrderItem[]
  tableId: string | null
  tabId: string | null
  customerId: string | null
  closedAt: string | null
  originDeviceId: string | null
  itemCount: number
}

export interface CreateOrderRequest {
  orderSource: OrderSource
  tableId?: string | null
  tabId?: string | null
  originDeviceId?: string | null
}

export interface AddOrderItemRequest {
  menuItemId: string
  quantity: number
  modifiersSnapshot?: Record<string, unknown>[]
}

export interface ListOrdersParams {
  offset?: number
  limit?: number
  tableId?: string
  status?: OrderStatus
}
