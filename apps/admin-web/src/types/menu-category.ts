/**
 * Mirrors modules/restaurant/presentation/api/v1/menu_category_router.py's
 * MenuCategoryResponseSchema / Create·Update MenuCategoryRequestSchema.
 * MenuCategory belongs to Restaurant, not Branch (Architecture SS3.1),
 * so it carries no branchId. Field names are camelCase on the wire.
 */

export interface MenuCategory {
  id: string
  tenantId: string
  restaurantId: string
  name: string
  displayOrder: number
  createdAt: string
}

export interface CreateMenuCategoryRequest {
  name: string
  displayOrder?: number
}

export type UpdateMenuCategoryRequest = CreateMenuCategoryRequest

export interface ListMenuCategoriesParams {
  offset?: number
  limit?: number
}
