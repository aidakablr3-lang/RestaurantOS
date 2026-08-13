/**
 * Dedicated fetch client for the guest QR ordering routes
 * (/api/v1/qr/{token}/...). Deliberately separate from `apiClient`
 * (lib/api-client.ts): guest routes never send an Authorization header
 * (there is no logged-in session, ever), and the token-resolution
 * failure responses use ADR 0001's flat `{ error: "not_found" | "rate_limited" }`
 * body instead of the standard ApiErrorEnvelope -- `apiClient`'s parsing
 * assumes every non-2xx body has a `success`/`error.code` shape, which
 * would throw a confusing secondary error on a bad/revoked/throttled
 * token. Everything past resolution (create order, add item, submit,
 * poll status) uses the same standard ApiSuccessResponse/ApiErrorEnvelope
 * shape every other route in this codebase uses, so those cases reuse
 * the same parsing `apiClient` already established.
 */
import { ApiError, NetworkError } from "@/lib/api-client"
import type { ApiErrorEnvelope, ApiSuccessResponse } from "@/lib/api-types"

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

const REQUEST_TIMEOUT_MS = 15_000

export type GuestTokenErrorKind = "not_found" | "rate_limited"

export class GuestTokenError extends Error {
  kind: GuestTokenErrorKind
  constructor(kind: GuestTokenErrorKind) {
    super(
      kind === "not_found"
        ? "This QR code isn't valid. Please ask a staff member for help."
        : "Too many requests right now. Please wait a moment and try again."
    )
    this.name = "GuestTokenError"
    this.kind = kind
  }
}

interface GuestFlatError {
  error: GuestTokenErrorKind
}

function isFlatError(body: unknown): body is GuestFlatError {
  return (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof (body as { error: unknown }).error === "string"
  )
}

async function guestRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set("Content-Type", "application/json")

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
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

  const body = (await response.json()) as
    | ApiSuccessResponse<T>
    | ApiErrorEnvelope
    | GuestFlatError

  if ((response.status === 404 || response.status === 429) && isFlatError(body)) {
    throw new GuestTokenError(body.error)
  }

  const enveloped = body as ApiSuccessResponse<T> | ApiErrorEnvelope
  if (!enveloped.success) {
    throw new ApiError(enveloped.error.message, enveloped.error.code, response.status)
  }
  return enveloped.data
}

function jsonInit(method: string, body?: unknown): RequestInit {
  return { method, body: body === undefined ? undefined : JSON.stringify(body) }
}

export const guestApiClient = {
  get: <T>(path: string) => guestRequest<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => guestRequest<T>(path, jsonInit("POST", body)),
}
