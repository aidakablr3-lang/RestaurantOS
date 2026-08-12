import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  addPurchaseOrderItem,
  cancelPurchaseOrder,
  confirmGoodsReceipt,
  createPurchaseOrder,
  getPurchaseOrder,
  listPurchaseOrders,
  sendPurchaseOrder,
} from "@/lib/api/purchase-orders"
import type {
  AddPurchaseOrderItemRequest,
  ConfirmGoodsReceiptRequest,
  CreatePurchaseOrderRequest,
  ListPurchaseOrdersParams,
} from "@/types/purchase-order"

export const purchaseOrderKeys = {
  all: ["purchase-orders"] as const,
  lists: (branchId: string) => [...purchaseOrderKeys.all, "list", branchId] as const,
  list: (branchId: string, params: ListPurchaseOrdersParams) =>
    [...purchaseOrderKeys.lists(branchId), params] as const,
  details: (branchId: string) => [...purchaseOrderKeys.all, "detail", branchId] as const,
  detail: (branchId: string, purchaseOrderId: string) =>
    [...purchaseOrderKeys.details(branchId), purchaseOrderId] as const,
}

export function usePurchaseOrders(
  branchId: string,
  params: ListPurchaseOrdersParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: purchaseOrderKeys.list(branchId, params),
    queryFn: () => listPurchaseOrders(branchId, params),
    enabled: options?.enabled,
  })
}

export function usePurchaseOrder(
  branchId: string,
  purchaseOrderId: string | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: purchaseOrderKeys.detail(branchId, purchaseOrderId ?? ""),
    queryFn: () => getPurchaseOrder(branchId, purchaseOrderId as string),
    enabled: Boolean(purchaseOrderId) && (options?.enabled ?? true),
  })
}

function invalidatePurchaseOrder(
  queryClient: ReturnType<typeof useQueryClient>,
  branchId: string,
  purchaseOrderId: string
) {
  queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.detail(branchId, purchaseOrderId) })
  queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.lists(branchId) })
}

export function useCreatePurchaseOrder(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreatePurchaseOrderRequest) => createPurchaseOrder(branchId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.lists(branchId) })
    },
  })
}

export function useAddPurchaseOrderItem(branchId: string, purchaseOrderId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AddPurchaseOrderItemRequest) =>
      addPurchaseOrderItem(purchaseOrderId, body),
    onSuccess: () => invalidatePurchaseOrder(queryClient, branchId, purchaseOrderId),
  })
}

export function useSendPurchaseOrder(branchId: string, purchaseOrderId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => sendPurchaseOrder(purchaseOrderId),
    onSuccess: () => invalidatePurchaseOrder(queryClient, branchId, purchaseOrderId),
  })
}

export function useCancelPurchaseOrder(branchId: string, purchaseOrderId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => cancelPurchaseOrder(purchaseOrderId),
    onSuccess: () => invalidatePurchaseOrder(queryClient, branchId, purchaseOrderId),
  })
}

export function useConfirmGoodsReceipt(branchId: string, purchaseOrderId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ConfirmGoodsReceiptRequest) => confirmGoodsReceipt(purchaseOrderId, body),
    onSuccess: () => invalidatePurchaseOrder(queryClient, branchId, purchaseOrderId),
  })
}
