import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import TaxesPage from "./page"

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useTaxesMock = vi.fn()
vi.mock("@/hooks/use-bills", () => ({
  useCreateTax: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useTaxes: (...args: unknown[]) => useTaxesMock(...args),
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

describe("TaxesPage permission gating", () => {
  it("shows a restricted state without billing.manage or billing.read tenant-wide", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useTaxesMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<TaxesPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("shows the Add tax action and an empty state with billing.manage and no taxes yet", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasTenantWide: (p) => p === "billing.manage" }))
    useTaxesMock.mockReturnValue({
      data: { data: [] },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<TaxesPage />)

    expect(screen.getAllByText("Add tax").length).toBeGreaterThan(0)
    expect(screen.getByText("No taxes yet")).toBeInTheDocument()
  })

  it("lists real taxes returned by the API", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasTenantWide: (p) => p === "billing.manage" }))
    useTaxesMock.mockReturnValue({
      data: {
        data: [
          { id: "t1", tenantId: "ten1", name: "VAT", rate: "0.1000", isActive: true, createdAt: "2026-01-01T00:00:00Z" },
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<TaxesPage />)

    expect(screen.getByText("VAT")).toBeInTheDocument()
  })
})
