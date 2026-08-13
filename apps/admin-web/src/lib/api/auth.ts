import { apiClient } from "@/lib/api-client"
import type { LoginRequest, TokenPair } from "@/lib/api-types"

export function login(body: LoginRequest) {
  return apiClient.post<TokenPair>("/api/v1/auth/login", body)
}

export function refresh(body: { tenantId: string; refreshToken: string }) {
  return apiClient.post<TokenPair>("/api/v1/auth/refresh", body)
}

export function logout(body: { tenantId: string; refreshToken: string }) {
  return apiClient.post<void>("/api/v1/auth/logout", body)
}
