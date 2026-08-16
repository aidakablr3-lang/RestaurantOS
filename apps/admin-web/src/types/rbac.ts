/**
 * Mirrors modules/identity/presentation/api/v1/self_service_tenant_router.py's
 * GET /api/v1/me/permissions (ResolvedPermissionsResponseSchema). Frontend
 * RBAC built on this is for UI visibility/UX only -- the backend remains
 * the sole authoritative security boundary, and every route already
 * enforces its own permission checks independent of anything the client
 * sends or infers.
 */

export interface ResolvedPermissions {
  tenantWide: string[]
  byBranch: Record<string, string[]>
}

/**
 * Mirrors rbac_router.py's RoleResponseSchema / UserRoleResponseSchema
 * and the two grant-scoped routes: POST/GET /api/v1/rbac/roles,
 * POST /api/v1/rbac/user-roles.
 */
export interface Role {
  id: string
  tenantId: string | null
  name: string
  description: string | null
  defaultScope: "tenant" | "branch"
  isSystem: boolean
  isActive: boolean
}

export interface ListRolesParams {
  offset?: number
  limit?: number
}

export interface UserRole {
  id: string
  tenantId: string
  userId: string
  roleId: string
  branchId: string | null
  grantedAt: string
  grantedByUserId: string | null
}

export interface AssignUserRoleRequest {
  userId: string
  roleId: string
  branchId?: string | null
}
