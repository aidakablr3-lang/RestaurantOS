import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { createModifier, listModifiers, updateModifier } from "@/lib/api/modifiers"
import type { CreateModifierRequest, UpdateModifierRequest } from "@/types/modifier"

export const modifierKeys = {
  all: ["modifiers"] as const,
  lists: (modifierGroupId: string) => [...modifierKeys.all, "list", modifierGroupId] as const,
}

export function useModifiers(modifierGroupId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: modifierKeys.lists(modifierGroupId),
    queryFn: () => listModifiers(modifierGroupId),
    enabled: options?.enabled,
  })
}

export function useCreateModifier(modifierGroupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateModifierRequest
      idempotencyKey: string
    }) => createModifier(modifierGroupId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: modifierKeys.lists(modifierGroupId) })
    },
  })
}

export function useUpdateModifier(modifierGroupId: string, modifierId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateModifierRequest) =>
      updateModifier(modifierGroupId, modifierId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: modifierKeys.lists(modifierGroupId) })
    },
  })
}
