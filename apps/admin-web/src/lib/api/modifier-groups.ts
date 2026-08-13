import { apiClient } from "@/lib/api-client"
import type {
  CreateModifierGroupRequest,
  ListModifierGroupsParams,
  ModifierGroup,
  UpdateModifierGroupRequest,
} from "@/types/modifier-group"

const BASE = "/api/v1/modifier-groups"

export function listModifierGroups(params: ListModifierGroupsParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<ModifierGroup[]>(`${BASE}?${search.toString()}`)
}

export function getModifierGroup(modifierGroupId: string) {
  return apiClient.get<ModifierGroup>(`${BASE}/${modifierGroupId}`)
}

export function createModifierGroup(body: CreateModifierGroupRequest, idempotencyKey: string) {
  return apiClient.post<ModifierGroup>(BASE, body, { idempotencyKey })
}

export function updateModifierGroup(modifierGroupId: string, body: UpdateModifierGroupRequest) {
  return apiClient.patch<ModifierGroup>(`${BASE}/${modifierGroupId}`, body)
}
