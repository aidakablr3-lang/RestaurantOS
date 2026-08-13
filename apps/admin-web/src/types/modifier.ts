/**
 * Mirrors modules/restaurant/presentation/api/v1/modifier_router.py's
 * ModifierResponseSchema / Create·Update ModifierRequestSchema.
 * ``priceDelta`` travels as a JSON string, same Decimal-precision
 * reasoning as MenuItem's ``priceAmount``. The list route is
 * deliberately unpaginated on the backend (no offset/limit, no
 * PaginationMeta) -- mirrored here rather than inventing pagination
 * the API doesn't support.
 */

export interface Modifier {
  id: string
  tenantId: string
  modifierGroupId: string
  name: string
  priceDelta: string
  createdAt: string
}

export interface CreateModifierRequest {
  name: string
  priceDelta?: string
}

export type UpdateModifierRequest = CreateModifierRequest
