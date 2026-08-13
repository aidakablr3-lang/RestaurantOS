import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import InventoryItemDetailPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1", inventoryItemId: "i1" }),
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useInventoryItemMock = vi.fn()
const useStockMovementsMock = vi.fn()
vi.mock("@/hooks/use-inventory", () => ({
  useInventoryItem: (...args: unknown[]) => useInventoryItemMock(...args),
  useStockMovements: (...args: unknown[]) => useStockMovementsMock(...args),
  useRecordStockMovement: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/current-user", () => ({
  useCurrentUserId: () => "01ARZ3NDEKTSV4RRFFQ69G5FAV",
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

const item = {
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
}

describe("InventoryItemDetailPage permission gating", () => {
  it("shows a restricted state without inventory.read at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useInventoryItemMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })
    useStockMovementsMock.mockReturnValue({ data: undefined, isLoading: false })

    render(<InventoryItemDetailPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("shows the Record movement action with inventory.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useInventoryItemMock.mockReturnValue({ data: { data: item }, isLoading: false, isError: false, error: null, refetch: vi.fn() })
    useStockMovementsMock.mockReturnValue({ data: { data: [] }, isLoading: false })

    render(<InventoryItemDetailPage />)

    expect(screen.getByText("Record movement")).toBeInTheDocument()
    expect(screen.getByText("10.0000 kg")).toBeInTheDocument()
  })
})
