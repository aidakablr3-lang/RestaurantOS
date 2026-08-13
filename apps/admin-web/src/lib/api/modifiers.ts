import { apiClient } from "@/lib/api-client"
import type { CreateModifierRequest, Modifier, UpdateModifierRequest } from "@/types/modifier"

const BASE = (modifierGroupId: string) => `/api/v1/modifier-groups/${modifierGroupId}/modifiers`

// Deliberately unpaginated -- the backend's own list route takes no
// offset/limit and returns no PaginationMeta (see types/modifier.ts).
export function listModifiers(modifierGroupId: string) {
  return apiClient.get<Modifier[]>(BASE(modifierGroupId))
}

export function getModifier(modifierGroupId: string, modifierId: string) {
  return apiClient.get<Modifier>(`${BASE(modifierGroupId)}/${modifierId}`)
}

export function createModifier(
  modifierGroupId: string,
  body: CreateModifierRequest,
  idempotencyKey: string
) {
  return apiClient.post<Modifier>(BASE(modifierGroupId), body, { idempotencyKey })
}

export function updateModifier(
  modifierGroupId: string,
  modifierId: string,
  body: UpdateModifierRequest
) {
  return apiClient.patch<Modifier>(`${BASE(modifierGroupId)}/${modifierId}`, body)
}
