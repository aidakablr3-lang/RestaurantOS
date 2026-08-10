/**
 * Mirrors modules/restaurant/presentation/api/v1/branch_router.py's
 * schemas (BranchResponseSchema / BranchDetailResponseSchema /
 * Create·Update BranchRequestSchema / OperatingHoursEntry·Schema) and the
 * domain's BranchStatus StrEnum. Field names are camelCase on the wire.
 */

export type BranchStatus =
  | "opened"
  | "active"
  | "temporarily_closed"
  | "permanently_closed"

export interface Address {
  id: string
  line1: string | null
  city: string | null
  countryCode: string | null
  postalCode: string | null
}

export interface AddressInput {
  line1?: string | null
  city?: string | null
  countryCode?: string | null
  postalCode?: string | null
}

export interface Branch {
  id: string
  tenantId: string
  restaurantId: string
  name: string
  status: BranchStatus
  address: Address | null
  createdAt: string
}

export interface OperatingHoursEntry {
  id: string
  dayOfWeek: number
  isClosed: boolean
  opensAt: string | null
  closesAt: string | null
}

export interface BranchDetail extends Branch {
  operatingHours: OperatingHoursEntry[]
}

export interface CreateBranchRequest {
  name: string
  address?: AddressInput | null
}

export type UpdateBranchRequest = CreateBranchRequest

export interface OperatingHoursEntryInput {
  dayOfWeek: number
  isClosed?: boolean
  opensAt?: string | null
  closesAt?: string | null
}

export interface ListBranchesParams {
  offset?: number
  limit?: number
}
