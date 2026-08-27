import { apiClient } from "@/lib/api-client"

export function activateOwner(body: { token: string; newPassword: string }) {
  return apiClient.post<void>("/api/v1/owner-activation", body)
}
