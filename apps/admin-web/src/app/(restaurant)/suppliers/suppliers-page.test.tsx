import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import SuppliersPage from "./page"

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useSuppliersMock = vi.fn()
vi.mock("@/hooks/use-suppliers", () => ({
  useSuppliers: (...args: unknown[]) => useSuppliersMock(...args),
  useCreateSupplier: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateSupplier: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

describe("SuppliersPage permission gating", () => {
  it("shows a restricted state without purchasing.read tenant-wide", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useSuppliersMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<SuppliersPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("hides manage actions for a read-only user", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasTenantWide: (p) => p === "purchasing.read" }))
    useSuppliersMock.mockReturnValue({
      data: {
        data: [{ id: "s1", tenantId: "t1", name: "Fresh Foods Co", status: "active", createdAt: "2026-01-01T00:00:00Z", address: null }],
        meta: { total: 1, offset: 0, limit: 20 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<SuppliersPage />)

    expect(screen.getByText("Fresh Foods Co")).toBeInTheDocument()
    expect(screen.queryByText("Add supplier")).not.toBeInTheDocument()
  })

  it("shows manage actions for a user with purchasing.manage", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasTenantWide: (p) => p === "purchasing.read" || p === "purchasing.manage" })
    )
    useSuppliersMock.mockReturnValue({
      data: {
        data: [{ id: "s1", tenantId: "t1", name: "Fresh Foods Co", status: "active", createdAt: "2026-01-01T00:00:00Z", address: null }],
        meta: { total: 1, offset: 0, limit: 20 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<SuppliersPage />)

    expect(screen.getAllByText("Add supplier").length).toBeGreaterThan(0)
    expect(screen.getByLabelText("Edit Fresh Foods Co")).toBeInTheDocument()
  })
})
