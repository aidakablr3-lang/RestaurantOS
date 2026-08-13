/**
 * Mirrors modules/operations/presentation/api/v1/inventory_router.py's
 * InventoryCategoryResponseSchema / InventoryItemResponseSchema /
 * StockMovementResponseSchema / Create·Update·Record RequestSchemas.
 * ``ClientWritableMovementType`` deliberately excludes ``sale_deduction``
 * (system-internal) and ``receipt`` (Purchasing's own GoodsReceipt
 * confirmation flow) -- neither is ever POSTed directly by a client.
 * Field names are camelCase on the wire; money/quantity fields are
 * decimal strings.
 */

export type ClientWritableMovementType = "adjustment" | "waste" | "transfer"

export type StockMovementType = ClientWritableMovementType | "sale_deduction" | "receipt"

export interface InventoryCategory {
  id: string
  tenantId: string
  name: string
  createdAt: string
}

export interface CreateInventoryCategoryRequest {
  name: string
}

export interface InventoryItem {
  id: string
  tenantId: string
  branchId: string
  inventoryCategoryId: string
  name: string
  unit: string
  quantityOnHand: string
  createdAt: string
  reorderPoint: string | null
  allowNegativeStockOverride: boolean | null
}

export interface CreateInventoryItemRequest {
  inventoryCategoryId: string
  name: string
  unit: string
  reorderPoint?: string | null
  allowNegativeStockOverride?: boolean | null
}

export interface UpdateInventoryItemRequest {
  inventoryCategoryId: string
  name: string
  reorderPoint?: string | null
  allowNegativeStockOverride?: boolean | null
}

export interface StockMovement {
  id: string
  tenantId: string
  branchId: string
  inventoryItemId: string
  movementType: StockMovementType
  quantityDelta: string
  occurredAt: string
  createdAt: string
  referenceType: string | null
  referenceId: string | null
  idempotencyKey: string | null
}

export interface RecordStockMovementRequest {
  movementType: ClientWritableMovementType
  quantityDelta: string
  reason?: string | null
  approvedByUserId?: string | null
  referenceType?: string | null
  referenceId?: string | null
}

export interface ListInventoryItemsParams {
  offset?: number
  limit?: number
}

export interface ListStockMovementsParams {
  offset?: number
  limit?: number
}
