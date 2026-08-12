import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import PurchaseOrdersPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1" }),
  usePathname: () => "/branches/b1/purchase-orders",
  useRouter: () => ({ push: vi.fn() }),
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const usePurchaseOrdersMock = vi.fn()
vi.mock("@/hooks/use-purchase-orders", () => ({
  usePurchaseOrders: (...args: unknown[]) => usePurchaseOrdersMock(...args),
  useCreatePurchaseOrder: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/hooks/use-suppliers", () => ({
  useSuppliers: () => ({ data: { data: [] }, isLoading: false }),
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

describe("PurchaseOrdersPage permission gating", () => {
  it("shows a restricted state without purchasing.read at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    usePurchaseOrdersMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<PurchaseOrdersPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("lists purchase orders and shows the New purchase order action with purchasing.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    usePurchaseOrdersMock.mockReturnValue({
      data: {
        data: [
          { id: "po1", tenantId: "t1", branchId: "b1", supplierId: "s1", status: "draft", createdAt: "2026-01-01T00:00:00Z", items: [] },
        ],
        meta: { total: 1, offset: 0, limit: 20 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<PurchaseOrdersPage />)

    expect(screen.getAllByText("New purchase order").length).toBeGreaterThan(0)
    expect(screen.getByText("Draft")).toBeInTheDocument()
  })
})
