/**
 * Mirrors modules/restaurant/presentation/api/v1/modifier_group_router.py's
 * ModifierGroupResponseSchema / Create·Update ModifierGroupRequestSchema
 * and the domain's ModifierSelectionType StrEnum. ModifierGroup has no
 * FK parent (Data Architecture v2.0 Group F -- it belongs directly to
 * the tenant), unlike every other Restaurant Platform entity built so
 * far. Field names are camelCase on the wire.
 */

export type ModifierSelectionType = "single" | "multiple"

export interface ModifierGroup {
  id: string
  tenantId: string
  name: string
  selectionType: ModifierSelectionType
  createdAt: string
}

export interface CreateModifierGroupRequest {
  name: string
  selectionType: ModifierSelectionType
}

export type UpdateModifierGroupRequest = CreateModifierGroupRequest

export interface ListModifierGroupsParams {
  offset?: number
  limit?: number
}
