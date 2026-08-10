/**
 * Mirrors modules/restaurant/presentation/schemas/
 * menu_item_availability_schemas.py -- the availability-dimension twin
 * of MenuItemBranchPrice; see that type's own docstring for the flat
 * route / history-not-resolution reasoning, which applies identically
 * here.
 */

export interface MenuItemAvailability {
  id: string
  tenantId: string
  branchId: string
  menuItemId: string
  isAvailable: boolean
  effectiveFrom: string
  effectiveTo: string | null
  createdAt: string
}

export interface CreateMenuItemAvailabilityRequest {
  branchId: string
  isAvailable: boolean
  effectiveFrom: string
  effectiveTo?: string | null
}
