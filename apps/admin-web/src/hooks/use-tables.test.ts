import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useChangeTableStatus, useCreateTable } from "@/hooks/use-tables"
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

describe("useChangeTableStatus", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("posts to the flat /api/v1/tables/{id}/status route, not a branch-nested one", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: {
          id: "table1",
          tenantId: "t1",
          branchId: "b1",
          tableZoneId: "tz1",
          tableNumber: "12",
          capacity: 4,
          status: "occupied",
          createdAt: "2026-01-01T00:00:00Z",
        },
        meta: null,
      })
    )

    const { result } = renderHook(() => useChangeTableStatus("b1", "table1"), { wrapper: Wrapper })

    await result.current.mutateAsync({ status: "occupied", idempotencyKey: "key-1" })

    expect(mockFetch.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/tables/table1/status")
    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body as string)).toEqual({ status: "occupied" })
  })

  it("surfaces a validation error from the backend without inventing a transition graph client-side", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        { success: false, error: { code: "VALIDATION_ERROR", message: "location: value_error; " } },
        422
      )
    )

    const { result } = renderHook(() => useChangeTableStatus("b1", "table1"), { wrapper: Wrapper })

    await expect(
      result.current.mutateAsync({ status: "cleaning", idempotencyKey: "key-2" })
    ).rejects.toMatchObject({ code: "VALIDATION_ERROR", status: 422 })
  })
})

describe("useCreateTable", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("surfaces a duplicate table number as a 409 conflict", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        {
          success: false,
          error: { code: "TABLE_NUMBER_ALREADY_EXISTS", message: "A table numbered '12' already exists." },
        },
        409
      )
    )

    const { result } = renderHook(() => useCreateTable("b1"), { wrapper: Wrapper })

    await expect(
      result.current.mutateAsync({
        body: { tableZoneId: "tz1", tableNumber: "12", capacity: 4 },
        idempotencyKey: "key-1",
      })
    ).rejects.toMatchObject({ code: "TABLE_NUMBER_ALREADY_EXISTS", status: 409 })
  })

  it("waits (isPending) while the create request is in flight", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    let resolveFetch!: (value: Response) => void
    mockFetch.mockReturnValueOnce(new Promise<Response>((resolve) => (resolveFetch = resolve)))

    const { result } = renderHook(() => useCreateTable("b1"), { wrapper: Wrapper })

    result.current.mutate({
      body: { tableZoneId: "tz1", tableNumber: "1", capacity: 2 },
      idempotencyKey: "key-1",
    })

    await waitFor(() => expect(result.current.isPending).toBe(true))

    resolveFetch(
      jsonResponse({
        success: true,
        data: {
          id: "table1",
          tenantId: "t1",
          branchId: "b1",
          tableZoneId: "tz1",
          tableNumber: "1",
          capacity: 2,
          status: "available",
          createdAt: "2026-01-01T00:00:00Z",
        },
        meta: null,
      })
    )

    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(result.current.isSuccess).toBe(true)
  })
})
