import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { changeTableStatus, createTable, getTable, listTables, updateTable } from "@/lib/api/tables"
import type {
  CreateTableRequest,
  ListTablesParams,
  TableStatus,
  UpdateTableRequest,
} from "@/types/table"

export const tableKeys = {
  all: ["tables"] as const,
  lists: (branchId: string) => [...tableKeys.all, "list", branchId] as const,
  list: (branchId: string, params: ListTablesParams) =>
    [...tableKeys.lists(branchId), params] as const,
  details: (branchId: string) => [...tableKeys.all, "detail", branchId] as const,
  detail: (branchId: string, id: string) => [...tableKeys.details(branchId), id] as const,
}

export function useTables(
  branchId: string,
  params: ListTablesParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: tableKeys.list(branchId, params),
    queryFn: () => listTables(branchId, params),
    enabled: options?.enabled,
  })
}

export function useTable(
  branchId: string,
  tableId: string | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: tableKeys.detail(branchId, tableId ?? ""),
    queryFn: () => getTable(branchId, tableId as string),
    enabled: Boolean(tableId) && (options?.enabled ?? true),
  })
}

export function useCreateTable(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateTableRequest
      idempotencyKey: string
    }) => createTable(branchId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tableKeys.lists(branchId) })
    },
  })
}

export function useUpdateTable(branchId: string, tableId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateTableRequest) => updateTable(branchId, tableId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tableKeys.detail(branchId, tableId) })
      queryClient.invalidateQueries({ queryKey: tableKeys.lists(branchId) })
    },
  })
}

// branchId is only needed here to invalidate this branch's cached list/
// detail entries -- the mutation itself calls the flat, table-id-only
// status endpoint (see lib/api/tables.ts's own note on why that route has
// no branchId in its path).
export function useChangeTableStatus(branchId: string, tableId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      status,
      idempotencyKey,
    }: {
      status: TableStatus
      idempotencyKey: string
    }) => changeTableStatus(tableId, status, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tableKeys.detail(branchId, tableId) })
      queryClient.invalidateQueries({ queryKey: tableKeys.lists(branchId) })
    },
  })
}
