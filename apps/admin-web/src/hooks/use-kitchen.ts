import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { changeKitchenItemStatus, changeKitchenTicketStatus, listKitchenTickets } from "@/lib/api/kitchen"
import type {
  ChangeKitchenItemStatusRequest,
  ChangeKitchenTicketStatusRequest,
  ListKitchenTicketsParams,
} from "@/types/kitchen"

export const kitchenTicketKeys = {
  all: ["kitchen-tickets"] as const,
  lists: (branchId: string) => [...kitchenTicketKeys.all, "list", branchId] as const,
  list: (branchId: string, params: ListKitchenTicketsParams) =>
    [...kitchenTicketKeys.lists(branchId), params] as const,
}

export function useKitchenTickets(
  branchId: string,
  params: ListKitchenTicketsParams,
  options?: { enabled?: boolean; refetchInterval?: number }
) {
  return useQuery({
    queryKey: kitchenTicketKeys.list(branchId, params),
    queryFn: () => listKitchenTickets(branchId, params),
    enabled: options?.enabled,
    refetchInterval: options?.refetchInterval,
  })
}

export function useChangeKitchenTicketStatus(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      kitchenTicketId,
      body,
      idempotencyKey,
    }: {
      kitchenTicketId: string
      body: ChangeKitchenTicketStatusRequest
      idempotencyKey: string
    }) => changeKitchenTicketStatus(kitchenTicketId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: kitchenTicketKeys.lists(branchId) })
    },
  })
}

export function useChangeKitchenItemStatus(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      kitchenItemId,
      body,
      idempotencyKey,
    }: {
      kitchenItemId: string
      body: ChangeKitchenItemStatusRequest
      idempotencyKey: string
    }) => changeKitchenItemStatus(kitchenItemId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: kitchenTicketKeys.lists(branchId) })
    },
  })
}
