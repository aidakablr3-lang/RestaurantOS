/**
 * Mirrors modules/restaurant/presentation/api/v1/menu_item_router.py's
 * MenuItemResponseSchema / Create·Update MenuItemRequestSchema.
 * ``priceAmount`` travels as a JSON string (Pydantic Decimal
 * JSON-mode serialization) -- never treat it as a float, to avoid the
 * precision loss the backend itself uses Decimal to avoid.
 * ``recipeId`` is a reserved, unpopulated FK for a future Inventory
 * Platform (Architecture SS3.1) -- always null today.
 */

export type MenuItemStation = "kitchen" | "bar"

export interface MenuItem {
  id: string
  tenantId: string
  menuCategoryId: string
  name: string
  priceAmount: string
  currencyCode: string
  isAvailable: boolean
  displayOrder: number
  recipeId: string | null
  createdAt: string
  station: MenuItemStation
}

export interface CreateMenuItemRequest {
  name: string
  priceAmount: string
  currencyCode: string
  isAvailable?: boolean
  displayOrder?: number
  station?: MenuItemStation
}

export type UpdateMenuItemRequest = CreateMenuItemRequest

export interface ListMenuItemsParams {
  offset?: number
  limit?: number
}
