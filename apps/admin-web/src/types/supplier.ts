/**
 * Mirrors modules/operations/presentation/api/v1/purchasing_router.py's
 * SupplierResponseSchema / Create·Update SupplierRequestSchema and the
 * domain's SupplierStatus StrEnum. Reuses the restaurant module's own
 * Address/AddressInput shape (@/types/branch) -- Supplier's address is
 * the same reused Address concept Branch already uses. Field names are
 * camelCase on the wire.
 */

import type { Address, AddressInput } from "@/types/branch"

export type SupplierStatus = "active" | "inactive"

export interface Supplier {
  id: string
  tenantId: string
  name: string
  status: SupplierStatus
  createdAt: string
  address: Address | null
}

export interface CreateSupplierRequest {
  name: string
  address?: AddressInput | null
}

export interface UpdateSupplierRequest {
  name: string
  status: SupplierStatus
  address?: AddressInput | null
}

export interface ListSuppliersParams {
  offset?: number
  limit?: number
}
