import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import KitchenPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1" }),
  usePathname: () => "/branches/b1/kitchen",
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useKitchenTicketsMock = vi.fn()
vi.mock("@/hooks/use-kitchen", () => ({
  useKitchenTickets: (...args: unknown[]) => useKitchenTicketsMock(...args),
  useChangeKitchenTicketStatus: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useChangeKitchenItemStatus: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

describe("KitchenPage permission gating", () => {
  it("shows a restricted state for a user without kitchen.read at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useKitchenTicketsMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<KitchenPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
  })

  it("renders ticket cards without manage actions for a read-only user", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: (_id, p) => p === "kitchen.read" }))
    useKitchenTicketsMock.mockReturnValue({
      data: {
        data: [
          {
            id: "kt1",
            tenantId: "t1",
            orderId: "o1",
            station: "kitchen",
            status: "fired",
            createdAt: "2026-01-01T19:00:00Z",
            items: [
              { id: "ki1", kitchenTicketId: "kt1", orderItemId: "oi1", status: "queued", createdAt: "2026-01-01T19:00:00Z" },
            ],
          },
        ],
        meta: { total: 1, offset: 0, limit: 50 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<KitchenPage />)

    expect(screen.getByText("kitchen")).toBeInTheDocument()
    expect(screen.queryByText("Mark ticket in progress")).not.toBeInTheDocument()
  })

  it("shows manage actions for a user with kitchen.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useKitchenTicketsMock.mockReturnValue({
      data: {
        data: [
          {
            id: "kt1",
            tenantId: "t1",
            orderId: "o1",
            station: "kitchen",
            status: "fired",
            createdAt: "2026-01-01T19:00:00Z",
            items: [
              { id: "ki1", kitchenTicketId: "kt1", orderItemId: "oi1", status: "queued", createdAt: "2026-01-01T19:00:00Z" },
            ],
          },
        ],
        meta: { total: 1, offset: 0, limit: 50 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<KitchenPage />)

    expect(screen.getByText("Mark ticket in progress")).toBeInTheDocument()
    expect(screen.getByText("Mark in progress")).toBeInTheDocument()
  })
})
