import { apiClient } from "@/lib/api-client"
import type { AssignUserRoleRequest, ListRolesParams, Role, UserRole } from "@/types/rbac"

const ROLES_BASE = "/api/v1/rbac/roles"
const USER_ROLES_BASE = "/api/v1/rbac/user-roles"

export function listRoles(params: ListRolesParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 100))
  return apiClient.get<Role[]>(`${ROLES_BASE}?${search.toString()}`)
}

export function assignUserRole(body: AssignUserRoleRequest) {
  return apiClient.post<UserRole>(USER_ROLES_BASE, body)
}
