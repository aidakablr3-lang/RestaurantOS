import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import MenuCategoriesPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ restaurantId: "r1" }),
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useMenuCategoriesMock = vi.fn()
vi.mock("@/hooks/use-menu-categories", () => ({
  useMenuCategories: (...args: unknown[]) => useMenuCategoriesMock(...args),
  useCreateMenuCategory: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateMenuCategory: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

describe("MenuCategoriesPage permission gating", () => {
  it("shows a restricted state for a user without menu.read", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useMenuCategoriesMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<MenuCategoriesPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
    expect(screen.queryByText("Add category")).not.toBeInTheDocument()
  })

  it("hides the Add category action for a read-only user", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasTenantWide: (p) => p === "menu.read" })
    )
    useMenuCategoriesMock.mockReturnValue({
      data: { data: [], meta: { total: 0, offset: 0, limit: 20 } },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<MenuCategoriesPage />)

    expect(screen.getByText("No menu categories yet")).toBeInTheDocument()
    expect(screen.queryByText("Add category")).not.toBeInTheDocument()
  })

  it("shows the Add category action for a user with menu.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasTenantWide: () => true }))
    useMenuCategoriesMock.mockReturnValue({
      data: {
        data: [
          {
            id: "mc1",
            tenantId: "t1",
            restaurantId: "r1",
            name: "Appetizers",
            displayOrder: 0,
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
        meta: { total: 1, offset: 0, limit: 20 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<MenuCategoriesPage />)

    expect(screen.getAllByText("Add category").length).toBeGreaterThan(0)
    expect(screen.getByText("Appetizers")).toBeInTheDocument()
  })
})
