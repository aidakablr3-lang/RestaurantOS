import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { createTableZone, getTableZone, listTableZones, updateTableZone } from "@/lib/api/table-zones"
import type {
  CreateTableZoneRequest,
  ListTableZonesParams,
  UpdateTableZoneRequest,
} from "@/types/table-zone"

export const tableZoneKeys = {
  all: ["table-zones"] as const,
  lists: (branchId: string) => [...tableZoneKeys.all, "list", branchId] as const,
  list: (branchId: string, params: ListTableZonesParams) =>
    [...tableZoneKeys.lists(branchId), params] as const,
  details: (branchId: string) => [...tableZoneKeys.all, "detail", branchId] as const,
  detail: (branchId: string, id: string) => [...tableZoneKeys.details(branchId), id] as const,
}

export function useTableZones(
  branchId: string,
  params: ListTableZonesParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: tableZoneKeys.list(branchId, params),
    queryFn: () => listTableZones(branchId, params),
    enabled: options?.enabled,
  })
}

export function useTableZone(
  branchId: string,
  tableZoneId: string | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: tableZoneKeys.detail(branchId, tableZoneId ?? ""),
    queryFn: () => getTableZone(branchId, tableZoneId as string),
    enabled: Boolean(tableZoneId) && (options?.enabled ?? true),
  })
}

export function useCreateTableZone(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateTableZoneRequest
      idempotencyKey: string
    }) => createTableZone(branchId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tableZoneKeys.lists(branchId) })
    },
  })
}

export function useUpdateTableZone(branchId: string, tableZoneId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateTableZoneRequest) => updateTableZone(branchId, tableZoneId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tableZoneKeys.detail(branchId, tableZoneId) })
      queryClient.invalidateQueries({ queryKey: tableZoneKeys.lists(branchId) })
    },
  })
}
