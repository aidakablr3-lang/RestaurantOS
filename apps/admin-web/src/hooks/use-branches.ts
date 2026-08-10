import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  closeBranch,
  getBranch,
  listBranches,
  reopenBranch,
  replaceOperatingHours,
  updateBranch,
} from "@/lib/api/branches"
import type {
  ListBranchesParams,
  OperatingHoursEntryInput,
  UpdateBranchRequest,
} from "@/types/branch"

export const branchKeys = {
  all: ["branches"] as const,
  lists: () => [...branchKeys.all, "list"] as const,
  list: (params: ListBranchesParams) => [...branchKeys.lists(), params] as const,
  details: () => [...branchKeys.all, "detail"] as const,
  detail: (id: string) => [...branchKeys.details(), id] as const,
}

export function useBranches(params: ListBranchesParams) {
  return useQuery({
    queryKey: branchKeys.list(params),
    queryFn: () => listBranches(params),
  })
}

export function useBranch(branchId: string | undefined) {
  return useQuery({
    queryKey: branchKeys.detail(branchId ?? ""),
    queryFn: () => getBranch(branchId as string),
    enabled: Boolean(branchId),
  })
}

export function useUpdateBranch(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateBranchRequest) => updateBranch(branchId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: branchKeys.detail(branchId) })
      queryClient.invalidateQueries({ queryKey: branchKeys.lists() })
    },
  })
}

export function useCloseBranch(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (idempotencyKey: string) => closeBranch(branchId, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: branchKeys.detail(branchId) })
      queryClient.invalidateQueries({ queryKey: branchKeys.lists() })
    },
  })
}

export function useReopenBranch(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (idempotencyKey: string) => reopenBranch(branchId, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: branchKeys.detail(branchId) })
      queryClient.invalidateQueries({ queryKey: branchKeys.lists() })
    },
  })
}

export function useReplaceOperatingHours(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      entries,
      idempotencyKey,
    }: {
      entries: OperatingHoursEntryInput[]
      idempotencyKey: string
    }) => replaceOperatingHours(branchId, entries, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: branchKeys.detail(branchId) })
    },
  })
}
