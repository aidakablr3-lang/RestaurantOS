import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useAssignUserRole, useRoles } from "@/hooks/use-roles"
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

describe("useRoles / useAssignUserRole", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("lists roles through the real resource client", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: [
          {
            id: "role1",
            tenantId: "t1",
            name: "Waiter",
            description: null,
            defaultScope: "branch",
            isSystem: true,
            isActive: true,
          },
        ],
        meta: { total: 1, offset: 0, limit: 100 },
      })
    )

    const { result } = renderHook(() => useRoles({ limit: 100 }, { enabled: true }), {
      wrapper: Wrapper,
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockFetch.mock.calls[0][0]).toContain("/api/v1/rbac/roles")
    expect(result.current.data?.data[0].name).toBe("Waiter")
  })

  it("assigns a role with the target user/role/branch ids", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: {
          id: "ur1",
          tenantId: "t1",
          userId: "u1",
          roleId: "role1",
          branchId: "b1",
          grantedAt: "2026-01-01T00:00:00Z",
          grantedByUserId: "owner1",
        },
        meta: null,
      })
    )

    const { result } = renderHook(() => useAssignUserRole(), { wrapper: Wrapper })

    await result.current.mutateAsync({ userId: "u1", roleId: "role1", branchId: "b1" })

    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body as string)).toEqual({
      userId: "u1",
      roleId: "role1",
      branchId: "b1",
    })
  })

  it("surfaces an INSUFFICIENT_GRANT_AUTHORITY conflict from the backend's own delegation ceiling", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        {
          success: false,
          error: {
            code: "INSUFFICIENT_GRANT_AUTHORITY",
            message: "Cannot grant a permission you do not hold.",
          },
        },
        403
      )
    )

    const { result } = renderHook(() => useAssignUserRole(), { wrapper: Wrapper })

    await expect(
      result.current.mutateAsync({ userId: "u1", roleId: "role1" })
    ).rejects.toMatchObject({ code: "INSUFFICIENT_GRANT_AUTHORITY", status: 403 })
  })
})
