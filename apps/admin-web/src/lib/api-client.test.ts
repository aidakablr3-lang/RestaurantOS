import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError, NetworkError, apiClient } from "@/lib/api-client"
import { useAuthStore } from "@/stores/auth-store"

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

describe("apiClient", () => {
  beforeEach(() => {
    useAuthStore.setState({
      accessToken: "access-1",
      refreshToken: "refresh-1",
      tenantId: "tenant-1",
      email: "user@example.com",
    })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("returns data and meta on a successful response", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ success: true, data: { id: "r1" }, meta: { total: 1, offset: 0, limit: 20 } })
    )

    const result = await apiClient.get<{ id: string }>("/api/v1/restaurants/r1")

    expect(result.data).toEqual({ id: "r1" })
    expect(result.meta).toEqual({ total: 1, offset: 0, limit: 20 })
  })

  it("sends the Bearer token from the auth store", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: {}, meta: null }))

    await apiClient.get("/api/v1/restaurants")

    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect((init.headers as Headers).get("authorization")).toBe("Bearer access-1")
  })

  it("attaches an Idempotency-Key header when provided", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: {}, meta: null }))

    await apiClient.post("/api/v1/restaurants", { legalName: "x" }, { idempotencyKey: "key-1" })

    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect((init.headers as Headers).get("idempotency-key")).toBe("key-1")
  })

  it("issues a DELETE request and tolerates a 204 with no body", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }))

    const result = await apiClient.delete("/api/v1/rbac/user-roles/x")

    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect(init.method).toBe("DELETE")
    expect(result.data).toBeUndefined()
  })

  it("throws ApiError with the envelope's code, message, and status on failure", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        { success: false, error: { code: "BRANCH_NOT_FOUND", message: "Branch not found." } },
        404
      )
    )

    await expect(apiClient.get("/api/v1/branches/x")).rejects.toMatchObject({
      code: "BRANCH_NOT_FOUND",
      status: 404,
      message: "Branch not found.",
    })
  })

  it("does not clear the session on an ordinary enumeration-resistant 401", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ success: false, error: { code: "USER_NOT_FOUND", message: "Not found." } }, 401)
    )

    await expect(apiClient.get("/api/v1/whatever")).rejects.toThrow(ApiError)

    expect(useAuthStore.getState().accessToken).toBe("access-1")
  })

  it("clears the session when the refresh token itself has been revoked", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ success: false, error: { code: "SESSION_REVOKED", message: "Revoked." } }, 401)
    )

    await expect(apiClient.get("/api/v1/whatever")).rejects.toThrow(ApiError)

    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it("silently refreshes and retries once on an expired access token", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch
      .mockResolvedValueOnce(
        jsonResponse(
          { success: false, error: { code: "INVALID_ACCESS_TOKEN", message: "Expired." } },
          401
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({
          success: true,
          data: {
            accessToken: "access-2",
            refreshToken: "refresh-2",
            tokenType: "bearer",
            expiresIn: 900,
          },
          meta: null,
        })
      )
      .mockResolvedValueOnce(jsonResponse({ success: true, data: { id: "r1" }, meta: null }))

    const result = await apiClient.get<{ id: string }>("/api/v1/restaurants/r1")

    expect(result.data).toEqual({ id: "r1" })
    expect(mockFetch).toHaveBeenCalledTimes(3)
    expect(useAuthStore.getState().accessToken).toBe("access-2")

    const retryInit = mockFetch.mock.calls[2][1] as RequestInit
    expect((retryInit.headers as Headers).get("authorization")).toBe("Bearer access-2")
  })

  it("clears the session and gives up if the refresh call itself fails", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch
      .mockResolvedValueOnce(
        jsonResponse(
          { success: false, error: { code: "INVALID_ACCESS_TOKEN", message: "Expired." } },
          401
        )
      )
      .mockResolvedValueOnce(
        jsonResponse(
          { success: false, error: { code: "INVALID_REFRESH_TOKEN", message: "Invalid." } },
          401
        )
      )

    await expect(apiClient.get("/api/v1/restaurants/r1")).rejects.toThrow(ApiError)

    expect(mockFetch).toHaveBeenCalledTimes(2)
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it("dedupes concurrent refreshes into a single /auth/refresh call", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch
      .mockResolvedValueOnce(
        jsonResponse({ success: false, error: { code: "INVALID_ACCESS_TOKEN", message: "x" } }, 401)
      )
      .mockResolvedValueOnce(
        jsonResponse({ success: false, error: { code: "INVALID_ACCESS_TOKEN", message: "x" } }, 401)
      )
      .mockResolvedValueOnce(
        jsonResponse({
          success: true,
          data: {
            accessToken: "access-2",
            refreshToken: "refresh-2",
            tokenType: "bearer",
            expiresIn: 900,
          },
          meta: null,
        })
      )
      .mockResolvedValueOnce(jsonResponse({ success: true, data: { a: 1 }, meta: null }))
      .mockResolvedValueOnce(jsonResponse({ success: true, data: { b: 2 }, meta: null }))

    await Promise.all([apiClient.get("/api/v1/a"), apiClient.get("/api/v1/b")])

    const refreshCalls = mockFetch.mock.calls.filter(([url]) =>
      String(url).includes("/api/v1/auth/refresh")
    )
    expect(refreshCalls).toHaveLength(1)
    expect(mockFetch).toHaveBeenCalledTimes(5)
  })

  it("wraps a fetch-level failure in NetworkError", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"))

    await expect(apiClient.get("/api/v1/restaurants")).rejects.toThrow(NetworkError)
  })
})
