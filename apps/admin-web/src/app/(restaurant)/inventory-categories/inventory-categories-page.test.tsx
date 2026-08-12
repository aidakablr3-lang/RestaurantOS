import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import InventoryCategoriesPage from "./page"

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useInventoryCategoriesMock = vi.fn()
vi.mock("@/hooks/use-inventory", () => ({
  useInventoryCategories: (...args: unknown[]) => useInventoryCategoriesMock(...args),
  useCreateInventoryCategory: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function mockPerms(overrides: { hasTenantWide?: (permission: string) => boolean } = {}) {
  return {
    isLoading: false,
    hasTenantWide: overrides.hasTenantWide ?? (() => false),
    hasAtBranch: () => false,
    hasAnywhere: () => false,
    accessibleBranchIds: () => [],
  }
}

describe("InventoryCategoriesPage permission gating", () => {
  it("shows a restricted state without inventory.read tenant-wide", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useInventoryCategoriesMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<InventoryCategoriesPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("hides the Add category action for a read-only user", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasTenantWide: (p) => p === "inventory.read" }))
    useInventoryCategoriesMock.mockReturnValue({
      data: { data: [] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<InventoryCategoriesPage />)

    expect(screen.getByText("No inventory categories yet")).toBeInTheDocument()
    expect(screen.queryByText("Add category")).not.toBeInTheDocument()
  })

  it("lists categories and shows the Add category action with inventory.manage", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasTenantWide: (p) => p === "inventory.read" || p === "inventory.manage" })
    )
    useInventoryCategoriesMock.mockReturnValue({
      data: { data: [{ id: "c1", tenantId: "t1", name: "Produce", createdAt: "2026-01-01T00:00:00Z" }] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<InventoryCategoriesPage />)

    expect(screen.getAllByText("Add category").length).toBeGreaterThan(0)
    expect(screen.getByText("Produce")).toBeInTheDocument()
  })
})
