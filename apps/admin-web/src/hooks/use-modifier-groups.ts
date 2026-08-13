import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createModifierGroup,
  getModifierGroup,
  listModifierGroups,
  updateModifierGroup,
} from "@/lib/api/modifier-groups"
import type {
  CreateModifierGroupRequest,
  ListModifierGroupsParams,
  UpdateModifierGroupRequest,
} from "@/types/modifier-group"

export const modifierGroupKeys = {
  all: ["modifier-groups"] as const,
  lists: () => [...modifierGroupKeys.all, "list"] as const,
  list: (params: ListModifierGroupsParams) => [...modifierGroupKeys.lists(), params] as const,
  details: () => [...modifierGroupKeys.all, "detail"] as const,
  detail: (id: string) => [...modifierGroupKeys.details(), id] as const,
}

export function useModifierGroups(
  params: ListModifierGroupsParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: modifierGroupKeys.list(params),
    queryFn: () => listModifierGroups(params),
    enabled: options?.enabled,
  })
}

export function useModifierGroup(
  modifierGroupId: string | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: modifierGroupKeys.detail(modifierGroupId ?? ""),
    queryFn: () => getModifierGroup(modifierGroupId as string),
    enabled: Boolean(modifierGroupId) && (options?.enabled ?? true),
  })
}

export function useCreateModifierGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateModifierGroupRequest
      idempotencyKey: string
    }) => createModifierGroup(body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: modifierGroupKeys.lists() })
    },
  })
}

export function useUpdateModifierGroup(modifierGroupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateModifierGroupRequest) => updateModifierGroup(modifierGroupId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: modifierGroupKeys.detail(modifierGroupId) })
      queryClient.invalidateQueries({ queryKey: modifierGroupKeys.lists() })
    },
  })
}
