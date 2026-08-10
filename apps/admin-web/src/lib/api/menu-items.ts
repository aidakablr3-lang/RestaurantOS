import { apiClient } from "@/lib/api-client"
import type {
  CreateMenuItemAvailabilityRequest,
  MenuItemAvailability,
} from "@/types/menu-item-availability"
import type {
  CreateMenuItemBranchPriceRequest,
  MenuItemBranchPrice,
} from "@/types/menu-item-branch-price"
import type {
  MenuItemModifierGroups,
  ReplaceMenuItemModifierGroupsRequest,
} from "@/types/menu-item-modifier-groups"
import type {
  CreateMenuItemRequest,
  ListMenuItemsParams,
  MenuItem,
  UpdateMenuItemRequest,
} from "@/types/menu-item"

const BASE = (menuCategoryId: string) => `/api/v1/menu-categories/${menuCategoryId}/menu-items`

export function listMenuItems(menuCategoryId: string, params: ListMenuItemsParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<MenuItem[]>(`${BASE(menuCategoryId)}?${search.toString()}`)
}

export function getMenuItem(menuCategoryId: string, menuItemId: string) {
  return apiClient.get<MenuItem>(`${BASE(menuCategoryId)}/${menuItemId}`)
}

export function createMenuItem(
  menuCategoryId: string,
  body: CreateMenuItemRequest,
  idempotencyKey: string
) {
  return apiClient.post<MenuItem>(BASE(menuCategoryId), body, { idempotencyKey })
}

export function updateMenuItem(
  menuCategoryId: string,
  menuItemId: string,
  body: UpdateMenuItemRequest
) {
  return apiClient.patch<MenuItem>(`${BASE(menuCategoryId)}/${menuItemId}`, body)
}

// The following are all deliberately flat (no menuCategoryId in the path)
// -- mirrors POST /api/v1/tables/{id}/status's own established shape for
// a cross-cutting action route (see lib/api/tables.ts).
export function replaceMenuItemModifierGroups(
  menuItemId: string,
  body: ReplaceMenuItemModifierGroupsRequest,
  idempotencyKey: string
) {
  return apiClient.put<MenuItemModifierGroups>(
    `/api/v1/menu-items/${menuItemId}/modifier-groups`,
    body,
    { idempotencyKey }
  )
}

export function createMenuItemBranchPrice(
  menuItemId: string,
  body: CreateMenuItemBranchPriceRequest,
  idempotencyKey: string
) {
  return apiClient.put<MenuItemBranchPrice>(`/api/v1/menu-items/${menuItemId}/branch-price`, body, {
    idempotencyKey,
  })
}

export function listMenuItemBranchPrices(menuItemId: string) {
  return apiClient.get<MenuItemBranchPrice[]>(`/api/v1/menu-items/${menuItemId}/branch-price`)
}

export function createMenuItemAvailability(
  menuItemId: string,
  body: CreateMenuItemAvailabilityRequest,
  idempotencyKey: string
) {
  return apiClient.put<MenuItemAvailability>(
    `/api/v1/menu-items/${menuItemId}/availability`,
    body,
    { idempotencyKey }
  )
}

export function listMenuItemAvailabilities(menuItemId: string) {
  return apiClient.get<MenuItemAvailability[]>(`/api/v1/menu-items/${menuItemId}/availability`)
}
