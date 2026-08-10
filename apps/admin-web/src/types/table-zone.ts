/**
 * Mirrors modules/restaurant/presentation/api/v1/table_zone_router.py's
 * TableZoneResponseSchema / Create·Update TableZoneRequestSchema. Field
 * names are camelCase on the wire.
 */

export interface TableZone {
  id: string
  tenantId: string
  branchId: string
  name: string
  displayOrder: number
  createdAt: string
}

export interface CreateTableZoneRequest {
  name: string
  displayOrder?: number
}

export type UpdateTableZoneRequest = CreateTableZoneRequest

export interface ListTableZonesParams {
  offset?: number
  limit?: number
}
