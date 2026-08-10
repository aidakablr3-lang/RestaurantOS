import { apiClient } from "@/lib/api-client"
import type { ResolvedPermissions } from "@/types/rbac"

export function getMyPermissions() {
  return apiClient.get<ResolvedPermissions>("/api/v1/me/permissions")
}
