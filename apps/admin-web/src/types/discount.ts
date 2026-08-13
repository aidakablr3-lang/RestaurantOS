/**
 * Mirrors modules/operations/presentation/api/v1/discount_router.py's
 * DiscountResponseSchema / CreateDiscountRequestSchema and the domain's
 * DiscountType StrEnum. Field names are camelCase on the wire.
 */

export type DiscountType = "percentage" | "fixed_amount"

export interface Discount {
  id: string
  tenantId: string
  name: string
  discountType: DiscountType
  value: string
  requiresApproval: boolean
  createdAt: string
  maxValue: string | null
  activeFrom: string | null
  activeTo: string | null
}

export interface CreateDiscountRequest {
  name: string
  discountType: DiscountType
  value: string
  requiresApproval?: boolean
  maxValue?: string | null
  activeFrom?: string | null
  activeTo?: string | null
}

export interface ListDiscountsParams {
  offset?: number
  limit?: number
}
