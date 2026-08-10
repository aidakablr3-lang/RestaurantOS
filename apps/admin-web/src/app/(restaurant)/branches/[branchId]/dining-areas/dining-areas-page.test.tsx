import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import DiningAreasPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1" }),
  usePathname: () => "/branches/b1/dining-areas",
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useTableZonesMock = vi.fn()
vi.mock("@/hooks/use-table-zones", () => ({
  useTableZones: (...args: unknown[]) => useTableZonesMock(...args),
  useCreateTableZone: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateTableZone: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function mockPerms(overrides: { hasAtBranch?: (branchId: string, permission: string) => boolean } = {}) {
  return {
    isLoading: false,
    hasTenantWide: () => false,
    hasAtBranch: overrides.hasAtBranch ?? (() => false),
    hasAnywhere: () => false,
    accessibleBranchIds: () => [],
  }
}

describe("DiningAreasPage permission gating", () => {
  it("shows a restricted state for a user without table.read at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useTableZonesMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<DiningAreasPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
    expect(screen.queryByText("Add dining area")).not.toBeInTheDocument()
  })

  it("hides the Add dining area action for a read-only user", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: (_id, p) => p === "table.read" }))
    useTableZonesMock.mockReturnValue({
      data: { data: [], meta: { total: 0, offset: 0, limit: 20 } },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<DiningAreasPage />)

    expect(screen.getByText("No dining areas yet")).toBeInTheDocument()
    expect(screen.queryByText("Add dining area")).not.toBeInTheDocument()
  })

  it("shows the Add dining area action for a user with table.manage", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasAtBranch: () => true })
    )
    useTableZonesMock.mockReturnValue({
      data: {
        data: [{ id: "tz1", tenantId: "t1", branchId: "b1", name: "Patio", displayOrder: 0, createdAt: "2026-01-01T00:00:00Z" }],
        meta: { total: 1, offset: 0, limit: 20 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<DiningAreasPage />)

    expect(screen.getAllByText("Add dining area").length).toBeGreaterThan(0)
    expect(screen.getByText("Patio")).toBeInTheDocument()
  })
})
