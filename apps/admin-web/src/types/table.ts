/**
 * Mirrors modules/restaurant/presentation/api/v1/table_router.py's
 * TableResponseSchema / Create·Update TableRequestSchema / the domain's
 * TableStatus StrEnum. Field names are camelCase on the wire.
 *
 * ``status`` is deliberately absent from create/update requests -- the
 * backend exposes a dedicated ``POST /api/v1/tables/{id}/status`` route
 * instead (see ChangeTableStatusRequest below), and defines no
 * transition graph between the four statuses.
 */

export type TableStatus = "available" | "occupied" | "reserved" | "cleaning"

export interface Table {
  id: string
  tenantId: string
  branchId: string
  tableZoneId: string
  tableNumber: string
  capacity: number
  status: TableStatus
  createdAt: string
}

export interface CreateTableRequest {
  tableZoneId: string
  tableNumber: string
  capacity: number
}

export type UpdateTableRequest = CreateTableRequest

export interface ChangeTableStatusRequest {
  status: TableStatus
}

export interface ListTablesParams {
  offset?: number
  limit?: number
}
