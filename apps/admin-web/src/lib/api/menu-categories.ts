import { apiClient } from "@/lib/api-client"
import type {
  CreateMenuCategoryRequest,
  ListMenuCategoriesParams,
  MenuCategory,
  UpdateMenuCategoryRequest,
} from "@/types/menu-category"

const BASE = (restaurantId: string) => `/api/v1/restaurants/${restaurantId}/menu-categories`

export function listMenuCategories(restaurantId: string, params: ListMenuCategoriesParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<MenuCategory[]>(`${BASE(restaurantId)}?${search.toString()}`)
}

export function getMenuCategory(restaurantId: string, menuCategoryId: string) {
  return apiClient.get<MenuCategory>(`${BASE(restaurantId)}/${menuCategoryId}`)
}

export function createMenuCategory(
  restaurantId: string,
  body: CreateMenuCategoryRequest,
  idempotencyKey: string
) {
  return apiClient.post<MenuCategory>(BASE(restaurantId), body, { idempotencyKey })
}

export function updateMenuCategory(
  restaurantId: string,
  menuCategoryId: string,
  body: UpdateMenuCategoryRequest
) {
  return apiClient.patch<MenuCategory>(`${BASE(restaurantId)}/${menuCategoryId}`, body)
}
