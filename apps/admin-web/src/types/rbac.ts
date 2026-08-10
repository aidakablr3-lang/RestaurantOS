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
