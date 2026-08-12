import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import OrdersPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1" }),
  usePathname: () => "/branches/b1/orders",
  useRouter: () => ({ push: vi.fn() }),
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useOrdersMock = vi.fn()
vi.mock("@/hooks/use-orders", () => ({
  useOrders: (...args: unknown[]) => useOrdersMock(...args),
  useCreateOrder: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/hooks/use-tables", () => ({
  useTables: () => ({ data: { data: [], meta: { total: 0, offset: 0, limit: 100 } }, isLoading: false }),
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

describe("OrdersPage permission gating", () => {
  it("shows a restricted state for a user without order.read at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useOrdersMock.mockReturnValue({ data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() })

    render(<OrdersPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
    expect(screen.queryByText("New order")).not.toBeInTheDocument()
  })

  it("hides the New order action for a read-only user", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: (_id, p) => p === "order.read" }))
    useOrdersMock.mockReturnValue({
      data: { data: [], meta: { total: 0, offset: 0, limit: 20 } },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<OrdersPage />)

    expect(screen.getByText("No orders yet")).toBeInTheDocument()
    expect(screen.queryByText("New order")).not.toBeInTheDocument()
  })

  it("lists orders and shows the New order action for a user with order.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useOrdersMock.mockReturnValue({
      data: {
        data: [
          {
            id: "o1",
            tenantId: "t1",
            branchId: "b1",
            orderSource: "pos",
            status: "open",
            subtotalAmount: "0.0000",
            taxAmount: "0.0000",
            totalAmount: "0.0000",
            currencyCode: "USD",
            openedAt: "2026-01-01T19:00:00Z",
            createdAt: "2026-01-01T19:00:00Z",
            items: [],
            tableId: null,
            tabId: null,
            customerId: null,
            closedAt: null,
            originDeviceId: null,
          },
        ],
        meta: { total: 1, offset: 0, limit: 20 },
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<OrdersPage />)

    expect(screen.getAllByText("New order").length).toBeGreaterThan(0)
    expect(screen.getByText("POS (dine-in)")).toBeInTheDocument()
    expect(screen.getByText("Open")).toBeInTheDocument()
  })
})
