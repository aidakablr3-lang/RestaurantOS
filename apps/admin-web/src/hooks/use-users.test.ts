import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useCreateUser, useUsers } from "@/hooks/use-users"
import { useAuthStore } from "@/stores/auth-store"

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function Wrapper({ children }: { children: React.ReactNode }) {
  const [client] = React.useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } })
  )
  return React.createElement(QueryClientProvider, { client }, children)
}

describe("useUsers / useCreateUser", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("lists staff accounts through the real resource client", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: [
          {
            id: "u1",
            tenantId: "t1",
            email: "waiter@example.com",
            phone: null,
            status: "active",
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
        meta: { total: 1, offset: 0, limit: 20 },
      })
    )

    const { result } = renderHook(() => useUsers({ offset: 0, limit: 20 }, { enabled: true }), {
      wrapper: Wrapper,
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockFetch.mock.calls[0][0]).toContain("/api/v1/users")
    expect(result.current.data?.data[0].email).toBe("waiter@example.com")
  })

  it("creates a staff account and surfaces the one-time generated password", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: {
          id: "u2",
          tenantId: "t1",
          email: "manager@example.com",
          phone: null,
          status: "active",
          createdAt: "2026-01-01T00:00:00Z",
          generatedPassword: "a-generated-secret",
        },
        meta: null,
      })
    )

    const { result } = renderHook(() => useCreateUser(), { wrapper: Wrapper })

    const created = await result.current.mutateAsync({ email: "manager@example.com" })

    expect(created.data.generatedPassword).toBe("a-generated-secret")
    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect(init.method).toBe("POST")
  })

  it("surfaces a USER_EMAIL_CONFLICT from the backend as an ApiError", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        {
          success: false,
          error: { code: "USER_EMAIL_CONFLICT", message: "A user with this email already exists." },
        },
        409
      )
    )

    const { result } = renderHook(() => useCreateUser(), { wrapper: Wrapper })

    await expect(result.current.mutateAsync({ email: "dup@example.com" })).rejects.toMatchObject({
      code: "USER_EMAIL_CONFLICT",
      status: 409,
    })
  })
})
