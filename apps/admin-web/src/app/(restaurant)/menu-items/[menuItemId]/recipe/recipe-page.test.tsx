import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import MenuItemRecipePage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ menuItemId: "mi1" }),
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

vi.mock("@/hooks/use-branches", () => ({
  useBranches: () => ({ data: { data: [] }, isLoading: false }),
}))

vi.mock("@/hooks/use-inventory", () => ({
  useInventoryItems: () => ({ data: { data: [] }, isLoading: false }),
}))

const useMenuItemRecipeMock = vi.fn()
vi.mock("@/hooks/use-recipes", () => ({
  useMenuItemRecipe: (...args: unknown[]) => useMenuItemRecipeMock(...args),
  useReviseRecipe: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

describe("MenuItemRecipePage permission gating", () => {
  it("shows a restricted state without menu.read tenant-wide", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useMenuItemRecipeMock.mockReturnValue({ data: undefined, isLoading: false, isError: true })

    render(<MenuItemRecipePage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("shows the no-recipe state and hides the revise form for a read-only user", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasTenantWide: (p) => p === "menu.read" }))
    useMenuItemRecipeMock.mockReturnValue({ data: undefined, isLoading: false, isError: true })

    render(<MenuItemRecipePage />)

    expect(screen.getByText("No recipe set for this menu item yet.")).toBeInTheDocument()
    expect(screen.queryByText("Revise recipe")).not.toBeInTheDocument()
  })

  it("shows the revise form for a user with menu.manage", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasTenantWide: (p) => p === "menu.read" || p === "menu.manage" })
    )
    useMenuItemRecipeMock.mockReturnValue({ data: undefined, isLoading: false, isError: true })

    render(<MenuItemRecipePage />)

    expect(screen.getByText("Revise recipe")).toBeInTheDocument()
  })
})
