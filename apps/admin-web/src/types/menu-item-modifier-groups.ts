/**
 * Mirrors modules/restaurant/presentation/schemas/
 * menu_item_modifier_group_schemas.py -- the MenuItem<->ModifierGroup
 * attachment endpoint. A full-replace operation (PUT), not an
 * incremental add/remove -- the caller always submits the complete
 * desired set of modifier group ids.
 */

export interface MenuItemModifierGroups {
  menuItemId: string
  modifierGroupIds: string[]
}

export interface ReplaceMenuItemModifierGroupsRequest {
  modifierGroupIds: string[]
}
