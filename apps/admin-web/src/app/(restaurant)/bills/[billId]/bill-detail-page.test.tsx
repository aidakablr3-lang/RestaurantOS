import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import BillDetailPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ billId: "bill1" }),
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useBillMock = vi.fn()
vi.mock("@/hooks/use-bills", () => ({
  useBill: (...args: unknown[]) => useBillMock(...args),
  useApplyBillAdjustment: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

const usePaymentsMock = vi.fn()
vi.mock("@/hooks/use-payments", () => ({
  usePayments: (...args: unknown[]) => usePaymentsMock(...args),
  useRecordPayment: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRequestRefund: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/current-user", () => ({
  useCurrentUserId: () => "01ARZ3NDEKTSV4RRFFQ69G5FAV",
}))

function mockPerms(overrides: { hasAnywhere?: (permission: string) => boolean } = {}) {
  return {
    isLoading: false,
    hasTenantWide: () => false,
    hasAtBranch: () => false,
    hasAnywhere: overrides.hasAnywhere ?? (() => false),
    accessibleBranchIds: () => [],
  }
}

const bill = {
  id: "bill1",
  tenantId: "t1",
  branchId: "b1",
  status: "open" as const,
  createdAt: "2026-01-01T00:00:00Z",
  orderId: "o1",
  tabId: null,
  subtotalAmount: "20.0000",
  taxAmount: "2.0000",
  adjustmentsTotal: "0.0000",
  amountDue: "22.0000",
  amountPaid: "0.0000",
  taxLines: [],
  adjustments: [],
}

describe("BillDetailPage permission gating", () => {
  it("shows a restricted state for a user without billing.read anywhere", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useBillMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })
    usePaymentsMock.mockReturnValue({ data: undefined, isLoading: false })

    render(<BillDetailPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("hides manage actions for a read-only user", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAnywhere: (p) => p === "billing.read" }))
    useBillMock.mockReturnValue({ data: { data: bill }, isLoading: false, isError: false, error: null, refetch: vi.fn() })
    usePaymentsMock.mockReturnValue({ data: { data: [] }, isLoading: false })

    render(<BillDetailPage />)

    expect(screen.getByText("Summary")).toBeInTheDocument()
    expect(screen.queryByText("Apply adjustment")).not.toBeInTheDocument()
    expect(screen.queryByText("Record payment")).not.toBeInTheDocument()
  })

  it("shows manage actions for a user with billing.manage", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasAnywhere: (p) => p === "billing.read" || p === "billing.manage" })
    )
    useBillMock.mockReturnValue({ data: { data: bill }, isLoading: false, isError: false, error: null, refetch: vi.fn() })
    usePaymentsMock.mockReturnValue({ data: { data: [] }, isLoading: false })

    render(<BillDetailPage />)

    expect(screen.getByText("Apply adjustment")).toBeInTheDocument()
    expect(screen.getByText("Record payment")).toBeInTheDocument()
  })
})
