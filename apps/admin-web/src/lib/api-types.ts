/**
 * Mirrors services/api's ApiResponse/ApiErrorResponse envelope
 * (restaurant_os_api/core/response.py) and the Tenant Administration
 * schemas (modules/identity/presentation/schemas/tenant_schemas.py).
 * Field names are camelCase on the wire.
 */

export interface PaginationMeta {
  total: number
  offset: number
  limit: number
}

export interface ApiSuccessResponse<T> {
  success: true
  data: T
  meta: PaginationMeta | null
}

export interface ApiErrorDetail {
  code: string
  message: string
}

export interface ApiErrorEnvelope {
  success: false
  error: ApiErrorDetail
}

// Lowercase, matching the domain's TenantStatus StrEnum values exactly
// (modules/identity/domain/entities/tenant.py) -- these are serialized
// as-is on the wire, not upper-cased.
export type TenantStatus =
  | "provisioning"
  | "active"
  | "suspended"
  | "migrating"
  | "offboarded"

export interface Tenant {
  id: string
  legalName: string
  displayName: string
  tenantTier: string
  status: TenantStatus
  defaultCurrencyCode: string
  metadata: Record<string, unknown>
  createdAt: string
  // Only present on the onboard response -- the owner activation token
  // is shown exactly once and never retrievable again (see
  // TenantResponseSchema's own docstring on the backend).
  ownerId?: string
  ownerEmail?: string
  ownerActivationToken?: string
}

export interface OnboardTenantRequest {
  legalName: string
  displayName: string
  defaultCurrencyCode: string
  ownerEmail: string
  ownerPhone?: string
}

export interface UpdateTenantRequest {
  displayName: string
  metadata: Record<string, unknown>
}

export interface ListTenantsParams {
  offset?: number
  limit?: number
  status?: string
}

export interface TokenPair {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresIn: number
}

export interface LoginRequest {
  tenantId: string
  email: string
  password: string
  deviceId?: string
}
