import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useCreateModifier, useModifiers } from "@/hooks/use-modifiers"
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

describe("useModifiers / useCreateModifier", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("lists modifiers for a group with no pagination params (the backend's list route is unpaginated)", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: [
          {
            id: "m1",
            tenantId: "t1",
            modifierGroupId: "mg1",
            name: "Extra cheese",
            priceDelta: "1.50",
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
        meta: null,
      })
    )

    const { result } = renderHook(() => useModifiers("mg1", { enabled: true }), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://localhost:8000/api/v1/modifier-groups/mg1/modifiers"
    )
  })

  it("allows a negative price delta and surfaces a validation error from the backend", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        { success: false, error: { code: "VALIDATION_ERROR", message: "location: value_error; " } },
        422
      )
    )

    const { result } = renderHook(() => useCreateModifier("mg1"), { wrapper: Wrapper })

    await expect(
      result.current.mutateAsync({
        body: { name: "No cheese", priceDelta: "-0.50" },
        idempotencyKey: "key-1",
      })
    ).rejects.toMatchObject({ code: "VALIDATION_ERROR", status: 422 })
  })
})
