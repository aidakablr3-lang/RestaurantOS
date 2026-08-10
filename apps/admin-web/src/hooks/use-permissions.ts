import { useQuery } from "@tanstack/react-query"

import { getMyPermissions } from "@/lib/api/permissions"
import { useAuthStore } from "@/stores/auth-store"

export const permissionsQueryKey = ["me", "permissions"] as const

export function usePermissionsQuery() {
  const accessToken = useAuthStore((state) => state.accessToken)
  return useQuery({
    queryKey: permissionsQueryKey,
    queryFn: () => getMyPermissions().then((result) => result.data),
    enabled: Boolean(accessToken),
    staleTime: 60_000,
  })
}

/**
 * Reusable can-see/can-manage helpers built on GET /api/v1/me/permissions.
 * This is a UI-visibility layer only -- every route on the backend
 * enforces its own permission check independent of what these return, so
 * a stale or manipulated client-side answer here can hide or show a
 * button, never actually authorize a request.
 */
export function usePermissionHelpers() {
  const { data, isLoading } = usePermissionsQuery()

  function hasTenantWide(permission: string): boolean {
    return data?.tenantWide.includes(permission) ?? false
  }

  function hasAtBranch(branchId: string, permission: string): boolean {
    if (hasTenantWide(permission)) return true
    return data?.byBranch[branchId]?.includes(permission) ?? false
  }

  function hasAnywhere(permission: string): boolean {
    if (hasTenantWide(permission)) return true
    if (!data) return false
    return Object.values(data.byBranch).some((perms) => perms.includes(permission))
  }

  function accessibleBranchIds(permission?: string): string[] {
    if (!data) return []
    if (!permission || hasTenantWide(permission)) return Object.keys(data.byBranch)
    return Object.entries(data.byBranch)
      .filter(([, perms]) => perms.includes(permission))
      .map(([branchId]) => branchId)
  }

  return { isLoading, hasTenantWide, hasAtBranch, hasAnywhere, accessibleBranchIds }
}
