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

vi.mock("@/hooks/use-cash-drawers", () => ({
  useOpenCashDrawer: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCloseCashDrawer: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

    render(<CashDrawerPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("shows the open-drawer form with billing.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))

    render(<CashDrawerPage />)

    expect(screen.getByText("Open a drawer")).toBeInTheDocument()
    expect(screen.getByText("Open drawer")).toBeInTheDocument()
  })
})
