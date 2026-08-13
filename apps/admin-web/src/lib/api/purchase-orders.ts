import { apiClient } from "@/lib/api-client"
import type {
  AddPurchaseOrderItemRequest,
  ConfirmGoodsReceiptRequest,
  CreatePurchaseOrderRequest,
  GoodsReceipt,
  ListPurchaseOrdersParams,
  PurchaseOrder,
} from "@/types/purchase-order"

const BRANCH_BASE = (branchId: string) => `/api/v1/branches/${branchId}/purchase-orders`

export function listPurchaseOrders(branchId: string, params: ListPurchaseOrdersParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<PurchaseOrder[]>(`${BRANCH_BASE(branchId)}?${search.toString()}`)
}

export function getPurchaseOrder(branchId: string, purchaseOrderId: string) {
  return apiClient.get<PurchaseOrder>(`${BRANCH_BASE(branchId)}/${purchaseOrderId}`)
}

export function createPurchaseOrder(branchId: string, body: CreatePurchaseOrderRequest) {
  return apiClient.post<PurchaseOrder>(BRANCH_BASE(branchId), body)
}

export function addPurchaseOrderItem(
  purchaseOrderId: string,
  body: AddPurchaseOrderItemRequest
) {
  return apiClient.post<PurchaseOrder>(`/api/v1/purchase-orders/${purchaseOrderId}/items`, body)
}

export function sendPurchaseOrder(purchaseOrderId: string) {
  return apiClient.post<PurchaseOrder>(`/api/v1/purchase-orders/${purchaseOrderId}/send`, undefined)
}

export function cancelPurchaseOrder(purchaseOrderId: string) {
  return apiClient.post<PurchaseOrder>(`/api/v1/purchase-orders/${purchaseOrderId}/cancel`, undefined)
}

export function confirmGoodsReceipt(purchaseOrderId: string, body: ConfirmGoodsReceiptRequest) {
  return apiClient.post<GoodsReceipt>(`/api/v1/purchase-orders/${purchaseOrderId}/receipts`, body)
}
