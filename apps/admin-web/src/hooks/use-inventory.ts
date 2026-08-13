import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createInventoryCategory,
  createInventoryItem,
  getInventoryItem,
  listInventoryCategories,
  listInventoryItems,
  listStockMovements,
  recordStockMovement,
  updateInventoryItem,
} from "@/lib/api/inventory"
import type {
  CreateInventoryCategoryRequest,
  CreateInventoryItemRequest,
  ListInventoryItemsParams,
  ListStockMovementsParams,
  RecordStockMovementRequest,
  UpdateInventoryItemRequest,
} from "@/types/inventory"

export const inventoryCategoryKeys = {
  all: ["inventory-categories"] as const,
  lists: () => [...inventoryCategoryKeys.all, "list"] as const,
}

export const inventoryItemKeys = {
  all: ["inventory-items"] as const,
  lists: (branchId: string) => [...inventoryItemKeys.all, "list", branchId] as const,
  list: (branchId: string, params: ListInventoryItemsParams) =>
    [...inventoryItemKeys.lists(branchId), params] as const,
  details: (branchId: string) => [...inventoryItemKeys.all, "detail", branchId] as const,
  detail: (branchId: string, inventoryItemId: string) =>
    [...inventoryItemKeys.details(branchId), inventoryItemId] as const,
}

export const stockMovementKeys = {
  all: ["stock-movements"] as const,
  lists: (inventoryItemId: string) => [...stockMovementKeys.all, "list", inventoryItemId] as const,
  list: (inventoryItemId: string, params: ListStockMovementsParams) =>
    [...stockMovementKeys.lists(inventoryItemId), params] as const,
}

export function useInventoryCategories(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: inventoryCategoryKeys.lists(),
    queryFn: () => listInventoryCategories(),
    enabled: options?.enabled,
  })
}

export function useCreateInventoryCategory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateInventoryCategoryRequest) => createInventoryCategory(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: inventoryCategoryKeys.lists() })
    },
  })
}

export function useInventoryItems(
  branchId: string,
  params: ListInventoryItemsParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: inventoryItemKeys.list(branchId, params),
    queryFn: () => listInventoryItems(branchId, params),
    enabled: options?.enabled,
  })
}

export function useInventoryItem(
  branchId: string,
  inventoryItemId: string | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: inventoryItemKeys.detail(branchId, inventoryItemId ?? ""),
    queryFn: () => getInventoryItem(branchId, inventoryItemId as string),
    enabled: Boolean(inventoryItemId) && (options?.enabled ?? true),
  })
}

export function useCreateInventoryItem(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateInventoryItemRequest) => createInventoryItem(branchId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: inventoryItemKeys.lists(branchId) })
    },
  })
}

export function useUpdateInventoryItem(branchId: string, inventoryItemId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateInventoryItemRequest) =>
      updateInventoryItem(branchId, inventoryItemId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: inventoryItemKeys.detail(branchId, inventoryItemId) })
      queryClient.invalidateQueries({ queryKey: inventoryItemKeys.lists(branchId) })
    },
  })
}

export function useStockMovements(
  inventoryItemId: string | undefined,
  params: ListStockMovementsParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: stockMovementKeys.list(inventoryItemId ?? "", params),
    queryFn: () => listStockMovements(inventoryItemId as string, params),
    enabled: Boolean(inventoryItemId) && (options?.enabled ?? true),
  })
}

export function useRecordStockMovement(branchId: string, inventoryItemId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: RecordStockMovementRequest) => recordStockMovement(inventoryItemId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: stockMovementKeys.lists(inventoryItemId) })
      queryClient.invalidateQueries({ queryKey: inventoryItemKeys.detail(branchId, inventoryItemId) })
      queryClient.invalidateQueries({ queryKey: inventoryItemKeys.lists(branchId) })
    },
  })
}
