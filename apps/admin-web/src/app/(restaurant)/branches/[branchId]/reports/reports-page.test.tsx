import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import EndOfDayReportPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1" }),
  usePathname: () => "/branches/b1/reports",
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useEndOfDayReportMock = vi.fn()
vi.mock("@/hooks/use-reports", () => ({
  useEndOfDayReport: (...args: unknown[]) => useEndOfDayReportMock(...args),
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

const REPORT = {
  branchId: "b1",
  reportDate: "2026-08-12",
  currencyCode: "USD",
  orderCount: 12,
  voidedOrderCount: 1,
  itemsSoldCount: 30,
  grossSalesAmount: "300.0000",
  voidedSalesAmount: "10.0000",
  outstandingAmount: "15.0000",
  totalCollectedAmount: "290.0000",
  totalTipsAmount: "20.0000",
  totalRefundedAmount: "5.0000",
  netCollectedAmount: "285.0000",
  tenderBreakdown: [
    { tenderType: "cash", amount: "100.0000", paymentCount: 4 },
    { tenderType: "card", amount: "190.0000", paymentCount: 8 },
  ],
  topItems: [{ menuItemId: "m1", name: "Burger", quantitySold: 15 }],
}

describe("EndOfDayReportPage", () => {
  it("shows a restricted state without reports.read at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useEndOfDayReportMock.mockReturnValue({ data: undefined, isLoading: false, isError: false })

    render(<EndOfDayReportPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("shows a loading state while the report is fetching", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useEndOfDayReportMock.mockReturnValue({ data: undefined, isLoading: true, isError: false })

    const { container } = render(<EndOfDayReportPage />)

    expect(container.querySelectorAll("[data-slot='skeleton']").length).toBeGreaterThan(0)
  })

  it("renders KPI cards, tender breakdown, and top items once loaded", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useEndOfDayReportMock.mockReturnValue({
      data: { data: REPORT },
      isLoading: false,
      isError: false,
    })

    render(<EndOfDayReportPage />)

    expect(screen.getByText("$300.00")).toBeInTheDocument()
    expect(screen.getByText("$285.00")).toBeInTheDocument()
    expect(screen.getByText("$15.00")).toBeInTheDocument()
    expect(screen.getByText("cash")).toBeInTheDocument()
    expect(screen.getByText("card")).toBeInTheDocument()
    expect(screen.getByText("Burger")).toBeInTheDocument()
    expect(screen.getByText("15")).toBeInTheDocument()
  })

  it("shows an empty-state message for a day with no settled payments", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useEndOfDayReportMock.mockReturnValue({
      data: { data: { ...REPORT, tenderBreakdown: [], topItems: [] } },
      isLoading: false,
      isError: false,
    })

    render(<EndOfDayReportPage />)

    expect(screen.getByText("No settled payments this day.")).toBeInTheDocument()
    expect(screen.getByText("No items sold this day.")).toBeInTheDocument()
  })
})
