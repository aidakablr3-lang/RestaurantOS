import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import DiscountsPage from "./page"

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useDiscountsMock = vi.fn()
vi.mock("@/hooks/use-discounts", () => ({
  useDiscounts: (...args: unknown[]) => useDiscountsMock(...args),
  useCreateDiscount: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

describe("DiscountsPage permission gating", () => {
  it("shows a restricted state without billing.manage tenant-wide", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useDiscountsMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<DiscountsPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
    expect(screen.queryByText("Add discount")).not.toBeInTheDocument()
  })

  it("lists discounts and shows the Add discount action with billing.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasTenantWide: (p) => p === "billing.manage" }))
    useDiscountsMock.mockReturnValue({
      data: {
        data: [
          {
            id: "d1",
            tenantId: "t1",
            name: "Staff meal",
            discountType: "percentage",
            value: "50",
            requiresApproval: true,
            createdAt: "2026-01-01T00:00:00Z",
            maxValue: null,
            activeFrom: null,
            activeTo: null,
          },
        ],
        meta: { total: 1, offset: 0, limit: 20 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<DiscountsPage />)

    expect(screen.getAllByText("Add discount").length).toBeGreaterThan(0)
    expect(screen.getByText("Staff meal")).toBeInTheDocument()
    expect(screen.getByText("Required")).toBeInTheDocument()
  })
})
