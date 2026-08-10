import { apiClient } from "@/lib/api-client"
import type {
  CreateTableRequest,
  ListTablesParams,
  Table,
  TableStatus,
  UpdateTableRequest,
} from "@/types/table"

const BASE = (branchId: string) => `/api/v1/branches/${branchId}/tables`

export function listTables(branchId: string, params: ListTablesParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<Table[]>(`${BASE(branchId)}?${search.toString()}`)
}

export function getTable(branchId: string, tableId: string) {
  return apiClient.get<Table>(`${BASE(branchId)}/${tableId}`)
}

export function createTable(branchId: string, body: CreateTableRequest, idempotencyKey: string) {
  return apiClient.post<Table>(BASE(branchId), body, { idempotencyKey })
}

export function updateTable(branchId: string, tableId: string, body: UpdateTableRequest) {
  return apiClient.patch<Table>(`${BASE(branchId)}/${tableId}`, body)
}

// Deliberately flat (no branchId in the path) -- mirrors the backend's own
// POST /api/v1/tables/{id}/status route, which Architecture SS7 places
// outside the branch-nested collection so a future Edge sync engine can
// call it directly. The backend resolves the table's real branch and
// authorizes against it server-side; the frontend still scopes UI
// visibility to the branch the table is being viewed from.
export function changeTableStatus(
  tableId: string,
  status: TableStatus,
  idempotencyKey: string
) {
  return apiClient.post<Table>(`/api/v1/tables/${tableId}/status`, { status }, { idempotencyKey })
}
