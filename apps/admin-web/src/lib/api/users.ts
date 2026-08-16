import { apiClient } from "@/lib/api-client"
import type { CreateUserRequest, ListUsersParams, User } from "@/types/user"

const BASE = "/api/v1/users"

export function listUsers(params: ListUsersParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<User[]>(`${BASE}?${search.toString()}`)
}

export function createUser(body: CreateUserRequest) {
  return apiClient.post<User>(BASE, body)
}
