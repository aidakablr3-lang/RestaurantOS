import { apiClient } from "@/lib/api-client"
import type {
  ListTenantsParams,
  OnboardTenantRequest,
  Tenant,
  UpdateTenantRequest,
} from "@/lib/api-types"

const BASE = "/api/v1/admin/tenants"

export function listTenants(params: ListTenantsParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  if (params.status) {
    search.set("status", params.status)
  }
  return apiClient.get<Tenant[]>(`${BASE}?${search.toString()}`)
}

export function getTenant(tenantId: string) {
  return apiClient.get<Tenant>(`${BASE}/${tenantId}`)
}

export function createTenant(body: OnboardTenantRequest) {
  return apiClient.post<Tenant>(BASE, body)
}

export function updateTenant(tenantId: string, body: UpdateTenantRequest) {
  return apiClient.patch<Tenant>(`${BASE}/${tenantId}`, body)
}

export function suspendTenant(tenantId: string) {
  return apiClient.post<Tenant>(`${BASE}/${tenantId}/suspend`)
}

export function reactivateTenant(tenantId: string) {
  return apiClient.post<Tenant>(`${BASE}/${tenantId}/reactivate`)
}
