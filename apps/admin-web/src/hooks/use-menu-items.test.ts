import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  useCreateMenuItemAvailability,
  useCreateMenuItemBranchPrice,
  useMenuItemBranchPrices,
  useReplaceMenuItemModifierGroups,
} from "@/hooks/use-menu-items"
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

describe("useReplaceMenuItemModifierGroups", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("PUTs to the flat /api/v1/menu-items/{id}/modifier-groups route with the full desired set", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: { menuItemId: "item1", modifierGroupIds: ["mg1", "mg2"] },
        meta: null,
      })
    )

    const { result } = renderHook(() => useReplaceMenuItemModifierGroups("cat1", "item1"), {
      wrapper: Wrapper,
    })

    const { data } = await result.current.mutateAsync({
      body: { modifierGroupIds: ["mg1", "mg2"] },
      idempotencyKey: "key-1",
    })

    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://localhost:8000/api/v1/menu-items/item1/modifier-groups"
    )
    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect(init.method).toBe("PUT")
    expect(data.modifierGroupIds).toEqual(["mg1", "mg2"])
  })
})

describe("useCreateMenuItemBranchPrice / useMenuItemBranchPrices", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("creates a branch price override and surfaces an EFFECTIVE_WINDOW_OVERLAP conflict", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        {
          success: false,
          error: { code: "EFFECTIVE_WINDOW_OVERLAP", message: "Overlaps an existing override." },
        },
        409
      )
    )

    const { result } = renderHook(() => useCreateMenuItemBranchPrice("item1"), { wrapper: Wrapper })

    await expect(
      result.current.mutateAsync({
        body: {
          branchId: "branch1",
          priceAmount: "9.99",
          effectiveFrom: "2026-01-01T00:00:00.000Z",
        },
        idempotencyKey: "key-1",
      })
    ).rejects.toMatchObject({ code: "EFFECTIVE_WINDOW_OVERLAP", status: 409 })

    expect(mockFetch.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/menu-items/item1/branch-price")
  })

  it("lists branch price overrides from the flat GET route", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: [
          {
            id: "bp1",
            tenantId: "t1",
            branchId: "branch1",
            menuItemId: "item1",
            priceAmount: "9.99",
            effectiveFrom: "2026-01-01T00:00:00Z",
            effectiveTo: null,
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
        meta: null,
      })
    )

    const { result } = renderHook(() => useMenuItemBranchPrices("item1", { enabled: true }), {
      wrapper: Wrapper,
    })

    await vi.waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.data).toHaveLength(1)
  })
})

describe("useCreateMenuItemAvailability", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("PUTs to the flat /api/v1/menu-items/{id}/availability route", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: {
          id: "av1",
          tenantId: "t1",
          branchId: "branch1",
          menuItemId: "item1",
          isAvailable: false,
          effectiveFrom: "2026-01-01T00:00:00Z",
          effectiveTo: null,
          createdAt: "2026-01-01T00:00:00Z",
        },
        meta: null,
      })
    )

    const { result } = renderHook(() => useCreateMenuItemAvailability("item1"), { wrapper: Wrapper })

    await result.current.mutateAsync({
      body: {
        branchId: "branch1",
        isAvailable: false,
        effectiveFrom: "2026-01-01T00:00:00.000Z",
      },
      idempotencyKey: "key-1",
    })

    expect(mockFetch.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/menu-items/item1/availability")
    const init = mockFetch.mock.calls[0][1] as RequestInit
    expect(init.method).toBe("PUT")
  })
})
