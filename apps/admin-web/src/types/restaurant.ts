/**
 * Mirrors modules/restaurant/presentation/api/v1/restaurant_router.py's
 * schemas (RestaurantResponseSchema / CreateRestaurantRequestSchema /
 * UpdateRestaurantRequestSchema) and the domain's RestaurantStatus StrEnum.
 * Field names are camelCase on the wire.
 */

export type RestaurantStatus = "active" | "discontinued"

export interface Restaurant {
  id: string
  tenantId: string
  legalName: string
  displayName: string
  defaultCurrencyCode: string
  status: RestaurantStatus
  createdAt: string
}

export interface CreateRestaurantRequest {
  legalName: string
  displayName: string
  defaultCurrencyCode: string
}

export type UpdateRestaurantRequest = CreateRestaurantRequest

export interface ListRestaurantsParams {
  offset?: number
  limit?: number
}
