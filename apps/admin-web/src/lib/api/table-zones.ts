import { apiClient } from "@/lib/api-client"
import type {
  CreateTableZoneRequest,
  ListTableZonesParams,
  TableZone,
  UpdateTableZoneRequest,
} from "@/types/table-zone"

const BASE = (branchId: string) => `/api/v1/branches/${branchId}/table-zones`

export function listTableZones(branchId: string, params: ListTableZonesParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<TableZone[]>(`${BASE(branchId)}?${search.toString()}`)
}

export function getTableZone(branchId: string, tableZoneId: string) {
  return apiClient.get<TableZone>(`${BASE(branchId)}/${tableZoneId}`)
}

export function createTableZone(
  branchId: string,
  body: CreateTableZoneRequest,
  idempotencyKey: string
) {
  return apiClient.post<TableZone>(BASE(branchId), body, { idempotencyKey })
}

export function updateTableZone(
  branchId: string,
  tableZoneId: string,
  body: UpdateTableZoneRequest
) {
  return apiClient.patch<TableZone>(`${BASE(branchId)}/${tableZoneId}`, body)
}
