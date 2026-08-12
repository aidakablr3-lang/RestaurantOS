import { apiClient } from "@/lib/api-client"
import type {
  CreateInventoryCategoryRequest,
  CreateInventoryItemRequest,
  InventoryCategory,
  InventoryItem,
  ListInventoryItemsParams,
  ListStockMovementsParams,
  RecordStockMovementRequest,
  StockMovement,
  UpdateInventoryItemRequest,
} from "@/types/inventory"

export function listInventoryCategories() {
  return apiClient.get<InventoryCategory[]>("/api/v1/inventory-categories")
}

export function createInventoryCategory(body: CreateInventoryCategoryRequest) {
  return apiClient.post<InventoryCategory>("/api/v1/inventory-categories", body)
}

export function listInventoryItems(branchId: string, params: ListInventoryItemsParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<InventoryItem[]>(
    `/api/v1/branches/${branchId}/inventory-items?${search.toString()}`
  )
}

export function getInventoryItem(branchId: string, inventoryItemId: string) {
  return apiClient.get<InventoryItem>(`/api/v1/branches/${branchId}/inventory-items/${inventoryItemId}`)
}

export function createInventoryItem(branchId: string, body: CreateInventoryItemRequest) {
  return apiClient.post<InventoryItem>(`/api/v1/branches/${branchId}/inventory-items`, body)
}

export function updateInventoryItem(
  branchId: string,
  inventoryItemId: string,
  body: UpdateInventoryItemRequest
) {
  return apiClient.patch<InventoryItem>(
    `/api/v1/branches/${branchId}/inventory-items/${inventoryItemId}`,
    body
  )
}

export function recordStockMovement(inventoryItemId: string, body: RecordStockMovementRequest) {
  return apiClient.post<StockMovement>(
    `/api/v1/inventory-items/${inventoryItemId}/stock-movements`,
    body
  )
}

export function listStockMovements(inventoryItemId: string, params: ListStockMovementsParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<StockMovement[]>(
    `/api/v1/inventory-items/${inventoryItemId}/stock-movements?${search.toString()}`
  )
}
