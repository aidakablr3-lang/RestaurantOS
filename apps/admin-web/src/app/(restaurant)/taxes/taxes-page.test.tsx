import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import TaxesPage from "./page"

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

vi.mock("@/hooks/use-bills", () => ({
  useCreateTax: () => ({ mutateAsync: vi.fn(), isPending: false }),
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
  it("shows a restricted state without billing.manage tenant-wide", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())

    render(<TaxesPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("shows the Add tax action with billing.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasTenantWide: (p) => p === "billing.manage" }))

    render(<TaxesPage />)

    expect(screen.getAllByText("Add tax").length).toBeGreaterThan(0)
    expect(screen.getByText("No taxes created this session")).toBeInTheDocument()
  })
})
