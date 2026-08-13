import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import InventoryItemsPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1" }),
  usePathname: () => "/branches/b1/inventory-items",
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useInventoryItemsMock = vi.fn()
vi.mock("@/hooks/use-inventory", () => ({
  useInventoryItems: (...args: unknown[]) => useInventoryItemsMock(...args),
  useInventoryCategories: () => ({ data: { data: [] }, isLoading: false }),
  useCreateInventoryItem: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

describe("InventoryItemsPage permission gating", () => {
  it("shows a restricted state without inventory.read at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useInventoryItemsMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<InventoryItemsPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("lists items and shows the Add item action with inventory.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useInventoryItemsMock.mockReturnValue({
      data: {
        data: [
          {
            id: "i1",
            tenantId: "t1",
            branchId: "b1",
            inventoryCategoryId: "c1",
            name: "Tomatoes",
            unit: "kg",
            quantityOnHand: "10.0000",
            createdAt: "2026-01-01T00:00:00Z",
            reorderPoint: null,
            allowNegativeStockOverride: null,
          },
        ],
        meta: { total: 1, offset: 0, limit: 20 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<InventoryItemsPage />)

    expect(screen.getAllByText("Add item").length).toBeGreaterThan(0)
    expect(screen.getByText("Tomatoes")).toBeInTheDocument()
  })
})
