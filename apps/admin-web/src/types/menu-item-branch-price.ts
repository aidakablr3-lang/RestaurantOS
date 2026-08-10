/**
 * Mirrors modules/restaurant/presentation/schemas/
 * menu_item_branch_price_schemas.py. ``branchId`` arrives in the body
 * (the route is flat -- ``PUT``/``GET /api/v1/menu-items/{id}/
 * branch-price``), never in the URL. GET returns every override row
 * for the item across every branch the caller can see -- history, not
 * a single resolved "current" price (no effective-price resolution
 * algorithm exists yet).
 */

export interface MenuItemBranchPrice {
  id: string
  tenantId: string
  branchId: string
  menuItemId: string
  priceAmount: string
  effectiveFrom: string
  effectiveTo: string | null
  createdAt: string
}

export interface CreateMenuItemBranchPriceRequest {
  branchId: string
  priceAmount: string
  effectiveFrom: string
  effectiveTo?: string | null
}
