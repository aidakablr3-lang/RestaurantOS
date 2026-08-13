/**
 * Mirrors modules/operations/presentation/api/v1/purchasing_router.py's
 * PurchaseOrderResponseSchema / PurchaseOrderItemResponseSchema /
 * GoodsReceiptResponseSchema / Create·Add·Confirm RequestSchemas and the
 * domain's PurchaseOrderStatus / GoodsReceiptStatus StrEnums. Field names
 * are camelCase on the wire; quantity fields are decimal strings.
 */

export type PurchaseOrderStatus =
  | "draft"
  | "sent"
  | "partially_received"
  | "fully_received"
  | "canceled"

export type GoodsReceiptStatus = "created" | "confirmed"

export interface PurchaseOrderItem {
  id: string
  purchaseOrderId: string
  inventoryItemId: string
  quantityOrdered: string
  quantityReceived: string
  createdAt: string
}

export interface PurchaseOrder {
  id: string
  tenantId: string
  branchId: string
  supplierId: string
  status: PurchaseOrderStatus
  createdAt: string
  items: PurchaseOrderItem[]
}

export interface CreatePurchaseOrderRequest {
  supplierId: string
}

export interface AddPurchaseOrderItemRequest {
  inventoryItemId: string
  quantityOrdered: string
}

export interface ConfirmGoodsReceiptLineRequest {
  purchaseOrderItemId: string
  quantityReceived: string
}

export interface ConfirmGoodsReceiptRequest {
  lines: ConfirmGoodsReceiptLineRequest[]
}

export interface GoodsReceipt {
  id: string
  tenantId: string
  purchaseOrderId: string
  status: GoodsReceiptStatus
  receivedAt: string
  createdAt: string
  hasDiscrepancy: boolean
  purchaseOrder: PurchaseOrder
}

export interface ListPurchaseOrdersParams {
  offset?: number
  limit?: number
}
