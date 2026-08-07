import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createTenant,
  getTenant,
  listTenants,
  reactivateTenant,
  suspendTenant,
  updateTenant,
} from "@/lib/api/tenants"
import type {
  ListTenantsParams,
  OnboardTenantRequest,
  UpdateTenantRequest,
} from "@/lib/api-types"

export const tenantKeys = {
  all: ["tenants"] as const,
  lists: () => [...tenantKeys.all, "list"] as const,
  list: (params: ListTenantsParams) => [...tenantKeys.lists(), params] as const,
  details: () => [...tenantKeys.all, "detail"] as const,
  detail: (id: string) => [...tenantKeys.details(), id] as const,
}

export function useTenants(params: ListTenantsParams) {
  return useQuery({
    queryKey: tenantKeys.list(params),
    queryFn: () => listTenants(params),
  })
}

export function useTenant(tenantId: string | undefined) {
  return useQuery({
    queryKey: tenantKeys.detail(tenantId ?? ""),
    queryFn: () => getTenant(tenantId as string),
    enabled: Boolean(tenantId),
  })
}

export function useCreateTenant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: OnboardTenantRequest) => createTenant(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tenantKeys.lists() })
    },
  })
}

export function useUpdateTenant(tenantId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateTenantRequest) => updateTenant(tenantId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tenantKeys.detail(tenantId) })
      queryClient.invalidateQueries({ queryKey: tenantKeys.lists() })
    },
  })
}

export function useSuspendTenant(tenantId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => suspendTenant(tenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tenantKeys.detail(tenantId) })
      queryClient.invalidateQueries({ queryKey: tenantKeys.lists() })
    },
  })
}

export function useReactivateTenant(tenantId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => reactivateTenant(tenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tenantKeys.detail(tenantId) })
      queryClient.invalidateQueries({ queryKey: tenantKeys.lists() })
    },
  })
}
