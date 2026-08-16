import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { assignUserRole, listRoles } from "@/lib/api/roles"
import { userKeys } from "@/hooks/use-users"
import type { AssignUserRoleRequest, ListRolesParams } from "@/types/rbac"

export const roleKeys = {
  all: ["roles"] as const,
  lists: () => [...roleKeys.all, "list"] as const,
  list: (params: ListRolesParams) => [...roleKeys.lists(), params] as const,
}

export function useRoles(params: ListRolesParams, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: roleKeys.list(params),
    queryFn: () => listRoles(params),
    enabled: options?.enabled,
  })
}

export function useAssignUserRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AssignUserRoleRequest) => assignUserRole(body),
    onSuccess: () => {
      // A grant doesn't change the user list itself, but the Staff
      // page's per-row "assigned roles" affordance (if/when it reads
      // grants back) would key off this same list -- invalidating here
      // keeps that future read fresh for free.
      queryClient.invalidateQueries({ queryKey: userKeys.lists() })
    },
  })
}
