import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useAuthStore } from "@/stores/auth-store"

vi.mock("@/lib/api/permissions", () => ({
  getMyPermissions: vi.fn().mockResolvedValue({
    data: {
      tenantWide: ["restaurant.manage", "restaurant.read"],
      byBranch: {
        "branch-1": ["table.manage", "reservation.read"],
        "branch-2": ["reservation.read"],
      },
    },
    meta: null,
  }),
}))

function Wrapper({ children }: { children: React.ReactNode }) {
  const [client] = React.useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } })
  )
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe("usePermissionHelpers", () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: "access-1", tenantId: "tenant-1" })
  })

  it("treats a tenant-wide permission as held everywhere", async () => {
    const { result } = renderHook(() => usePermissionHelpers(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.hasTenantWide("restaurant.manage")).toBe(true)
    expect(result.current.hasAtBranch("branch-99", "restaurant.manage")).toBe(true)
  })

  it("scopes a branch permission to the branches that actually grant it", async () => {
    const { result } = renderHook(() => usePermissionHelpers(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.hasAtBranch("branch-1", "table.manage")).toBe(true)
    expect(result.current.hasAtBranch("branch-2", "table.manage")).toBe(false)
    expect(result.current.hasAnywhere("table.manage")).toBe(true)
  })

  it("returns false for a permission held nowhere", async () => {
    const { result } = renderHook(() => usePermissionHelpers(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.hasAnywhere("menu.manage")).toBe(false)
  })

  it("lists only branches that grant the requested permission", async () => {
    const { result } = renderHook(() => usePermissionHelpers(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.accessibleBranchIds("table.manage")).toEqual(["branch-1"])
    expect(result.current.accessibleBranchIds("reservation.read").sort()).toEqual([
      "branch-1",
      "branch-2",
    ])
  })
})
