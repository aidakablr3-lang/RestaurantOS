import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AppSidebar, MobileNav } from "@/components/app-sidebar"
import type { usePermissionHelpers } from "@/hooks/use-permissions"

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

type Perms = ReturnType<typeof usePermissionHelpers>

function mockPerms(overrides: Partial<Perms> = {}): Perms {
  return {
    isLoading: false,
    hasTenantWide: () => false,
    hasAtBranch: () => false,
    hasAnywhere: () => false,
    accessibleBranchIds: () => [],
    ...overrides,
  }
}

describe("AppSidebar", () => {
  it("hides Restaurants and Branches links when the user holds neither permission", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())

    render(<AppSidebar />)

    expect(screen.getByText("Dashboard")).toBeInTheDocument()
    expect(screen.queryByText("Restaurants")).not.toBeInTheDocument()
    expect(screen.queryByText("Branches")).not.toBeInTheDocument()
  })

  it("shows Restaurants when the user holds restaurant.read tenant-wide", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasTenantWide: (p) => p === "restaurant.read" })
    )

    render(<AppSidebar />)

    expect(screen.getByText("Restaurants")).toBeInTheDocument()
    expect(screen.queryByText("Branches")).not.toBeInTheDocument()
  })

  it("shows Branches when the user holds branch.read at any scope", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasAnywhere: (p) => p === "branch.read" })
    )

    render(<AppSidebar />)

    expect(screen.getByText("Branches")).toBeInTheDocument()
    expect(screen.queryByText("Restaurants")).not.toBeInTheDocument()
  })

  it("shows both links while permissions are still loading, to avoid a flash of a missing link", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ isLoading: true }))

    render(<AppSidebar />)

    expect(screen.getByText("Restaurants")).toBeInTheDocument()
    expect(screen.getByText("Branches")).toBeInTheDocument()
  })

  it("always marks Reservations and Menu as coming soon, regardless of permissions", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({
        hasTenantWide: () => true,
        hasAnywhere: () => true,
      })
    )

    render(<AppSidebar />)

    expect(screen.getAllByText("Soon")).toHaveLength(2)
  })
})

// MobileNav backs the sidebar's `hidden md:flex` gap below the `md`
// breakpoint, where AppSidebar itself isn't reachable at all -- covers
// the click-to-open interaction this suite's browser session couldn't
// conclusively re-verify live (see docs/AI_HANDOFF.md's Step 6.1 section).
describe("MobileNav", () => {
  it("opens on click and lists the same permission-filtered links as the sidebar", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasTenantWide: (p) => p === "restaurant.read" })
    )

    render(<MobileNav />)

    expect(screen.queryByText("Restaurants")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Open navigation menu" }))

    expect(screen.getByText("Dashboard")).toBeInTheDocument()
    expect(screen.getByText("Restaurants")).toBeInTheDocument()
    expect(screen.queryByText("Branches")).not.toBeInTheDocument()
  })

  it("renders the coming-soon items as disabled, non-navigating entries", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())

    render(<MobileNav />)
    fireEvent.click(screen.getByRole("button", { name: "Open navigation menu" }))

    const reservations = screen.getByText("Reservations").closest('[role="menuitem"]')
    expect(reservations).toHaveAttribute("aria-disabled", "true")
  })
})
