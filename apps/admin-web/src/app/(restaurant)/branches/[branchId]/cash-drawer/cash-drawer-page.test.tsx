import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import CashDrawerPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1" }),
  usePathname: () => "/branches/b1/cash-drawer",
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useOpenCashDrawerLookupMock = vi.fn()
vi.mock("@/hooks/use-cash-drawers", () => ({
  useOpenCashDrawer: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCloseCashDrawer: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenCashDrawerLookup: (...args: unknown[]) => useOpenCashDrawerLookupMock(...args),
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

describe("CashDrawerPage permission gating", () => {
  it("shows a restricted state without billing.manage at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useOpenCashDrawerLookupMock.mockReturnValue({ data: undefined, isLoading: false })

    render(<CashDrawerPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("shows the open-drawer form with billing.manage when no drawer is open", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useOpenCashDrawerLookupMock.mockReturnValue({ data: { data: null }, isLoading: false })

    render(<CashDrawerPage />)

    expect(screen.getByText("Open a drawer")).toBeInTheDocument()
    expect(screen.getByText("Open drawer")).toBeInTheDocument()
  })

  it("recovers an already-open drawer after a reload instead of always showing the open form", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useOpenCashDrawerLookupMock.mockReturnValue({
      data: {
        data: {
          id: "d1",
          tenantId: "t1",
          branchId: "b1",
          status: "open",
          openingFloatAmount: "100.0000",
          openedAt: "2026-08-12T18:00:00Z",
          createdAt: "2026-08-12T18:00:00Z",
          terminalId: null,
          closingCountedAmount: null,
          closedAt: null,
          expectedCashAmount: null,
          varianceAmount: null,
        },
      },
      isLoading: false,
    })

    render(<CashDrawerPage />)

    expect(screen.getByText("Drawer open")).toBeInTheDocument()
    expect(screen.getByText("Close drawer")).toBeInTheDocument()
  })
})
