import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import PurchaseOrderDetailPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1", purchaseOrderId: "po1" }),
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const usePurchaseOrderMock = vi.fn()
vi.mock("@/hooks/use-purchase-orders", () => ({
  usePurchaseOrder: (...args: unknown[]) => usePurchaseOrderMock(...args),
  useAddPurchaseOrderItem: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSendPurchaseOrder: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCancelPurchaseOrder: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useConfirmGoodsReceipt: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/hooks/use-inventory", () => ({
  useInventoryItems: () => ({ data: { data: [] }, isLoading: false }),
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

const draftPO = {
  id: "po1",
  tenantId: "t1",
  branchId: "b1",
  supplierId: "s1",
  status: "draft" as const,
  createdAt: "2026-01-01T00:00:00Z",
  items: [],
}

describe("PurchaseOrderDetailPage permission gating", () => {
  it("shows a restricted state without purchasing.read at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    usePurchaseOrderMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<PurchaseOrderDetailPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("shows draft-stage manage actions with purchasing.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    usePurchaseOrderMock.mockReturnValue({ data: { data: draftPO }, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<PurchaseOrderDetailPage />)

    expect(screen.getByText("Add item")).toBeInTheDocument()
    expect(screen.getByText("Send to supplier")).toBeInTheDocument()
    expect(screen.getByText("Cancel")).toBeInTheDocument()
  })
})
