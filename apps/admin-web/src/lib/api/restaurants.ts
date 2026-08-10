import { apiClient } from "@/lib/api-client"
import type {
  CreateRestaurantRequest,
  ListRestaurantsParams,
  Restaurant,
  UpdateRestaurantRequest,
} from "@/types/restaurant"
import type { Branch, CreateBranchRequest } from "@/types/branch"

const BASE = "/api/v1/restaurants"

export function listRestaurants(params: ListRestaurantsParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<Restaurant[]>(`${BASE}?${search.toString()}`)
}

export function getRestaurant(restaurantId: string) {
  return apiClient.get<Restaurant>(`${BASE}/${restaurantId}`)
}

export function createRestaurant(
  body: CreateRestaurantRequest,
  idempotencyKey: string
) {
  return apiClient.post<Restaurant>(BASE, body, { idempotencyKey })
}

export function updateRestaurant(
  restaurantId: string,
  body: UpdateRestaurantRequest
) {
  return apiClient.patch<Restaurant>(`${BASE}/${restaurantId}`, body)
}

export function discontinueRestaurant(
  restaurantId: string,
  idempotencyKey: string
) {
  return apiClient.post<Restaurant>(
    `${BASE}/${restaurantId}/discontinue`,
    undefined,
    { idempotencyKey }
  )
}

export function createBranch(
  restaurantId: string,
  body: CreateBranchRequest,
  idempotencyKey: string
) {
  return apiClient.post<Branch>(`${BASE}/${restaurantId}/branches`, body, {
    idempotencyKey,
  })
}
