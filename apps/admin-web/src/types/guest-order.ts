/**
 * Mirrors modules/restaurant/presentation/schemas/guest_menu_schemas.py's
 * GuestMenuResponseSchema/GuestMenuCategoryResponseSchema/
 * GuestMenuItemResponseSchema. A distinct, minimal read model from the
 * staff-facing MenuItem/MenuCategory types in types/menu.ts -- a guest
 * never sees recipeId/station/unavailable items.
 */

export interface GuestMenuItem {
  id: string
  name: string
  priceAmount: string
  currencyCode: string
}

export interface GuestMenuCategory {
  id: string
  name: string
  displayOrder: number
  items: GuestMenuItem[]
}

export interface GuestMenu {
  branchId: string
  tableId: string
  restaurantName: string
  branchName: string
  tableNumber: string
  categories: GuestMenuCategory[]
}
