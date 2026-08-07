import { apiClient } from "@/lib/api-client"
import type { LoginRequest, TokenPair } from "@/lib/api-types"

export function login(body: LoginRequest) {
  return apiClient.post<TokenPair>("/api/v1/auth/login", body)
}
