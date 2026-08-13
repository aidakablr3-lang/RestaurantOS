import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useCreateTableZone, useTableZones } from "@/hooks/use-table-zones"
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

describe("useTableZones / useCreateTableZone", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("lists table zones for a branch through the real resource client", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: [{ id: "tz1", tenantId: "t1", branchId: "b1", name: "Patio", displayOrder: 0, createdAt: "2026-01-01T00:00:00Z" }],
        meta: { total: 1, offset: 0, limit: 20 },
      })
    )

    const { result } = renderHook(() => useTableZones("b1", { offset: 0, limit: 20 }, { enabled: true }), {
      wrapper: Wrapper,
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.data).toHaveLength(1)
    expect(mockFetch.mock.calls[0][0]).toContain("/api/v1/branches/b1/table-zones")
  })

  it("does not fire the request when disabled (e.g. permissions still loading)", () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>

    renderHook(() => useTableZones("b1", { offset: 0, limit: 20 }, { enabled: false }), {
      wrapper: Wrapper,
    })

    expect(mockFetch).not.toHaveBeenCalled()
  })

  it("creates a table zone with an Idempotency-Key and surfaces a name conflict", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        {
          success: false,
          error: { code: "TABLE_ZONE_NAME_CONFLICT", message: "A table zone named 'Patio' already exists." },
        },
        409
      )
    )

    const { result } = renderHook(() => useCreateTableZone("b1"), { wrapper: Wrapper })

    await expect(
      result.current.mutateAsync({ body: { name: "Patio", displayOrder: 0 }, idempotencyKey: "key-1" })
    ).rejects.toMatchObject({ code: "TABLE_ZONE_NAME_CONFLICT", status: 409 })

    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect((init.headers as Headers).get("idempotency-key")).toBe("key-1")
  })
})
