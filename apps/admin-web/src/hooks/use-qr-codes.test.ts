import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useGenerateQRCode, useQRCodes } from "@/hooks/use-qr-codes"
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

describe("useQRCodes", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("returns both revoked and active codes for a table's history", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: [
          {
            id: "qr1",
            tenantId: "t1",
            branchId: "b1",
            tableId: "table1",
            token: "old-token",
            status: "revoked",
            createdAt: "2026-01-01T00:00:00Z",
          },
          {
            id: "qr2",
            tenantId: "t1",
            branchId: "b1",
            tableId: "table1",
            token: "new-token",
            status: "active",
            createdAt: "2026-01-02T00:00:00Z",
          },
        ],
        meta: null,
      })
    )

    const { result } = renderHook(() => useQRCodes("table1", { enabled: true }), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const statuses = result.current.data?.data.map((code) => code.status)
    expect(statuses).toEqual(["revoked", "active"])
    expect(mockFetch.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/tables/table1/qr-codes")
  })

  it("does not fire when no tableId is given", () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>

    renderHook(() => useQRCodes(undefined), { wrapper: Wrapper })

    expect(mockFetch).not.toHaveBeenCalled()
  })
})

describe("useGenerateQRCode", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("posts with no body -- the table comes from the path, everything else is generated", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: {
          id: "qr3",
          tenantId: "t1",
          branchId: "b1",
          tableId: "table1",
          token: "fresh-token",
          status: "active",
          createdAt: "2026-01-03T00:00:00Z",
        },
        meta: null,
      })
    )

    const { result } = renderHook(() => useGenerateQRCode("table1"), { wrapper: Wrapper })

    const { data } = await result.current.mutateAsync("key-1")

    expect(data.status).toBe("active")
    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect(init.method).toBe("POST")
    expect(init.body).toBeUndefined()
    expect((init.headers as Headers).get("idempotency-key")).toBe("key-1")
  })
})
