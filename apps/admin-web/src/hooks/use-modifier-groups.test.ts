import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useCreateModifierGroup, useModifierGroups } from "@/hooks/use-modifier-groups"
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

describe("useModifierGroups / useCreateModifierGroup", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("lists modifier groups from the flat, tenant-wide collection path", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: [
          {
            id: "mg1",
            tenantId: "t1",
            name: "Toppings",
            selectionType: "multiple",
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
        meta: { total: 1, offset: 0, limit: 20 },
      })
    )

    const { result } = renderHook(() => useModifierGroups({ offset: 0, limit: 20 }, { enabled: true }), {
      wrapper: Wrapper,
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://localhost:8000/api/v1/modifier-groups?offset=0&limit=20"
    )
  })

  it("creates a modifier group and sends the selectionType field", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: {
          id: "mg2",
          tenantId: "t1",
          name: "Spice level",
          selectionType: "single",
          createdAt: "2026-01-01T00:00:00Z",
        },
        meta: null,
      })
    )

    const { result } = renderHook(() => useCreateModifierGroup(), { wrapper: Wrapper })

    await result.current.mutateAsync({
      body: { name: "Spice level", selectionType: "single" },
      idempotencyKey: "key-1",
    })

    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect(JSON.parse(init.body as string)).toEqual({
      name: "Spice level",
      selectionType: "single",
    })
  })
})
