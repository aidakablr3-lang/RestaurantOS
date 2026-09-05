import { useAuthStore } from "@/stores/auth-store"
import type {
  ApiErrorEnvelope,
  ApiSuccessResponse,
  PaginationMeta,
  TokenPair,
} from "@/lib/api-types"

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

const REQUEST_TIMEOUT_MS = 15_000

// INVALID_ACCESS_TOKEN means the access token itself expired or is
// malformed -- worth one silent refresh-and-retry. SESSION_REVOKED means
// the *refresh* token is dead (logged out elsewhere, revoked by an admin),
// so retrying would just fail again. Neither of these is the same as an
// ordinary 401 the API also uses for enumeration-resistant "not found"
// lookups (see TENANT_NOT_FOUND/USER_NOT_FOUND in the backend's
// core/exceptions.py) -- those must never trigger a refresh or a session
// clear.
const REFRESHABLE_ERROR_CODE = "INVALID_ACCESS_TOKEN"
const TOKEN_INVALID_ERROR_CODES = new Set([
  "INVALID_ACCESS_TOKEN",
  "SESSION_REVOKED",
])

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

export class NetworkError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "NetworkError"
  }
}

export interface ApiResult<T> {
  data: T
  meta: PaginationMeta | null
}

interface RequestOptions {
  idempotencyKey?: string
  // Menu-import extraction runs a vision call over several photos and
  // routinely takes longer than the default -- everything else keeps
  // the 15s default.
  timeoutMs?: number
}

// Several requests can 401 with an expired access token at once (e.g. a
// dashboard firing off parallel queries). Without this lock each one would
// call /auth/refresh independently, and the backend rotates the refresh
// token on every use -- the second call would arrive with an
// already-rotated token and get treated as reuse. Every request that hits
// a refreshable 401 while a refresh is already running awaits the same
// in-flight promise instead of starting its own.
let refreshInFlight: Promise<boolean> | null = null

function attemptRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = doRefresh().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

async function doRefresh(): Promise<boolean> {
  const { refreshToken, tenantId, setSession, clearSession } =
    useAuthStore.getState()
  if (!refreshToken || !tenantId) {
    return false
  }
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenantId, refreshToken }),
    })
    const body = (await response.json()) as
      | ApiSuccessResponse<TokenPair>
      | ApiErrorEnvelope
    if (!body.success) {
      clearSession()
      return false
    }
    setSession(body.data, tenantId)
    return true
  } catch {
    clearSession()
    return false
  }
}

async function rawRequest(
  path: string,
  init: RequestInit,
  idempotencyKey?: string,
  timeoutMs: number = REQUEST_TIMEOUT_MS
): Promise<Response> {
  const accessToken = useAuthStore.getState().accessToken
  const headers = new Headers(init.headers)
  // A FormData body (multipart file upload) must NOT get this header --
  // fetch sets its own Content-Type with the multipart boundary
  // automatically, and overriding it here would break the server's
  // multipart parser.
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json")
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`)
  }
  if (idempotencyKey) {
    headers.set("Idempotency-Key", idempotencyKey)
  }

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    })
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "AbortError"
    throw new NetworkError(
      timedOut
        ? "The request timed out. Please try again."
        : "Unable to reach the server. Check your connection and try again."
    )
  } finally {
    clearTimeout(timer)
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
  isRetry = false
): Promise<ApiResult<T>> {
  const response = await rawRequest(path, init, options.idempotencyKey, options.timeoutMs)

  if (response.status === 204) {
    return { data: undefined as T, meta: null }
  }

  const body = (await response.json()) as ApiSuccessResponse<T> | ApiErrorEnvelope

  if (!body.success) {
    if (!isRetry && body.error.code === REFRESHABLE_ERROR_CODE) {
      const refreshed = await attemptRefresh()
      if (refreshed) {
        return request<T>(path, init, options, true)
      }
    }
    if (TOKEN_INVALID_ERROR_CODES.has(body.error.code)) {
      useAuthStore.getState().clearSession()
    }
    throw new ApiError(body.error.message, body.error.code, response.status)
  }

  return { data: body.data, meta: body.meta }
}

function jsonInit(method: string, body?: unknown): RequestInit {
  return { method, body: body === undefined ? undefined : JSON.stringify(body) }
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, jsonInit("POST", body), options),
  postForm: <T>(path: string, body: FormData, options?: RequestOptions) =>
    request<T>(path, { method: "POST", body }, options),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, jsonInit("PATCH", body), options),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, jsonInit("PUT", body), options),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { method: "DELETE" }, options),
}
