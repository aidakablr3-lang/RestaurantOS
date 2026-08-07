import { useAuthStore } from "@/stores/auth-store"
import type { ApiErrorEnvelope, ApiSuccessResponse, PaginationMeta } from "@/lib/api-types"

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  code: string
  status: number

  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.code = code
    this.status = status
  }
}

export interface ApiResult<T> {
  data: T
  meta: PaginationMeta | null
}

async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<ApiResult<T>> {
  const accessToken = useAuthStore.getState().accessToken
  const headers = new Headers(init.headers)
  headers.set("Content-Type", "application/json")
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  })

  if (response.status === 401) {
    useAuthStore.getState().clearSession()
  }

  if (response.status === 204) {
    return { data: undefined as T, meta: null }
  }

  const body = (await response.json()) as
    | ApiSuccessResponse<T>
    | ApiErrorEnvelope

  if (!body.success) {
    throw new ApiError(body.error.message, body.error.code, response.status)
  }

  return { data: body.data, meta: body.meta }
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PUT",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
}
