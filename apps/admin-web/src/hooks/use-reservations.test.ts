import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useCreateReservation, useReservations, useUpdateReservation } from "@/hooks/use-reservations"
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

describe("useReservations / useCreateReservation", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("lists reservations for a branch through the real resource client", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: [
          {
            id: "res1",
            tenantId: "t1",
            branchId: "b1",
            tableId: null,
            customerId: null,
            partySize: 2,
            requestedAt: "2026-01-01T19:00:00Z",
            status: "requested",
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
        meta: { total: 1, offset: 0, limit: 20 },
      })
    )

    const { result } = renderHook(
      () => useReservations("b1", { offset: 0, limit: 20 }, { enabled: true }),
      { wrapper: Wrapper }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockFetch.mock.calls[0][0]).toContain("/api/v1/branches/b1/reservations")
    expect(result.current.data?.data[0].customerId).toBeNull()
  })

  it("creates a reservation with an Idempotency-Key and no customerId field", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: {
          id: "res2",
          tenantId: "t1",
          branchId: "b1",
          tableId: null,
          customerId: null,
          partySize: 4,
          requestedAt: "2026-01-01T19:00:00Z",
          status: "requested",
          createdAt: "2026-01-01T00:00:00Z",
        },
        meta: null,
      })
    )

    const { result } = renderHook(() => useCreateReservation("b1"), { wrapper: Wrapper })

    await result.current.mutateAsync({
      body: { partySize: 4, requestedAt: "2026-01-01T19:00:00.000Z" },
      idempotencyKey: "key-1",
    })

    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect((init.headers as Headers).get("idempotency-key")).toBe("key-1")
    expect(JSON.parse(init.body as string)).not.toHaveProperty("customerId")
  })
})

describe("useUpdateReservation", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("PATCHes with the target status alongside the unchanged partySize/tableId", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: {
          id: "res1",
          tenantId: "t1",
          branchId: "b1",
          tableId: "table1",
          customerId: null,
          partySize: 2,
          requestedAt: "2026-01-01T19:00:00Z",
          status: "confirmed",
          createdAt: "2026-01-01T00:00:00Z",
        },
        meta: null,
      })
    )

    const { result } = renderHook(() => useUpdateReservation("b1", "res1"), { wrapper: Wrapper })

    await result.current.mutateAsync({ partySize: 2, status: "confirmed", tableId: "table1" })

    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect(init.method).toBe("PATCH")
    expect(JSON.parse(init.body as string)).toEqual({
      partySize: 2,
      status: "confirmed",
      tableId: "table1",
    })
  })

  it("surfaces an INVALID_RESERVATION_STATUS_TRANSITION conflict from the backend's own graph", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        {
          success: false,
          error: {
            code: "INVALID_RESERVATION_STATUS_TRANSITION",
            message: "Cannot transition from completed to requested.",
          },
        },
        409
      )
    )

    const { result } = renderHook(() => useUpdateReservation("b1", "res1"), { wrapper: Wrapper })

    await expect(
      result.current.mutateAsync({ partySize: 2, status: "requested", tableId: null })
    ).rejects.toMatchObject({ code: "INVALID_RESERVATION_STATUS_TRANSITION", status: 409 })
  })
})
