import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import OrderDetailPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1", orderId: "o1" }),
  useRouter: () => ({ push: vi.fn() }),
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useOrderMock = vi.fn()
const useVoidOrderItemMock = vi.fn()
vi.mock("@/hooks/use-orders", () => ({
  useOrder: (...args: unknown[]) => useOrderMock(...args),
  useAddOrderItem: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useFireOrder: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCloseOrder: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useVoidOrder: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useVoidOrderItem: (...args: unknown[]) => useVoidOrderItemMock(...args),
}))

vi.mock("@/hooks/use-bills", () => ({
  useGenerateBill: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/hooks/use-branches", () => ({
  useBranch: () => ({ data: { data: { id: "b1", restaurantId: "r1" } } }),
}))

vi.mock("@/hooks/use-menu-items", () => ({
  useRestaurantMenuItems: () => ({ data: [], isLoading: false }),
}))

const useTablesMock = vi.fn()
vi.mock("@/hooks/use-tables", () => ({
  useTables: (...args: unknown[]) => useTablesMock(...args),
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

const baseOrder = {
  id: "o1",
  tenantId: "t1",
  branchId: "b1",
  orderSource: "pos" as const,
  status: "open" as const,
  subtotalAmount: "28.0000",
  taxAmount: "0.0000",
  totalAmount: "28.0000",
  currencyCode: "USD",
  openedAt: "2026-08-12T12:00:00Z",
  createdAt: "2026-08-12T12:00:00Z",
  items: [],
  tableId: "table-i02",
  tabId: null,
  customerId: null,
  closedAt: null,
  originDeviceId: null,
  itemCount: 0,
}

describe("OrderDetailPage table display", () => {
  beforeEach(() => {
    useVoidOrderItemMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, variables: undefined })
  })

  it("resolves the table id to its human-readable table number, not the raw id", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useOrderMock.mockReturnValue({ data: { data: baseOrder }, isLoading: false, isError: false, error: null, refetch: vi.fn() })
    useTablesMock.mockReturnValue({
      data: { data: [{ id: "table-i02", tableNumber: "I02" }], meta: { total: 1, offset: 0, limit: 100 } },
      isLoading: false,
    })

    render(<OrderDetailPage />)

    expect(screen.getByText("I02")).toBeInTheDocument()
    expect(screen.queryByText("table-i02")).not.toBeInTheDocument()
  })

  it("shows an em dash when the order has no table", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useOrderMock.mockReturnValue({
      data: { data: { ...baseOrder, tableId: null } },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })
    useTablesMock.mockReturnValue({ data: { data: [], meta: { total: 0, offset: 0, limit: 100 } }, isLoading: false })

    render(<OrderDetailPage />)

    expect(screen.getByText("—")).toBeInTheDocument()
  })
})

describe("OrderDetailPage item void", () => {
  beforeEach(() => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useTablesMock.mockReturnValue({ data: { data: [], meta: { total: 0, offset: 0, limit: 100 } }, isLoading: false })
  })

  const orderWithItems = {
    ...baseOrder,
    items: [
      {
        id: "item-1",
        orderId: "o1",
        menuItemId: "menu-1",
        quantity: 1,
        unitPriceAmount: "9.0000",
        lineStatus: "added" as const,
        createdAt: "2026-08-12T12:00:00Z",
        modifiersSnapshot: [],
        recipeCostSnapshot: null,
      },
      {
        id: "item-2",
        orderId: "o1",
        menuItemId: "menu-2",
        quantity: 1,
        unitPriceAmount: "9.0000",
        lineStatus: "fired" as const,
        createdAt: "2026-08-12T12:00:00Z",
        modifiersSnapshot: [],
        recipeCostSnapshot: null,
      },
    ],
  }

  it("shows a void button only for an added item, not a fired one", () => {
    useOrderMock.mockReturnValue({
      data: { data: orderWithItems },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<OrderDetailPage />)

    expect(screen.getAllByRole("button", { name: /^Void$/ })).toHaveLength(1)
  })

  it("calls the void-item mutation with the item id when confirmed", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    useVoidOrderItemMock.mockReturnValue({ mutateAsync, isPending: false, variables: undefined })
    useOrderMock.mockReturnValue({
      data: { data: orderWithItems },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<OrderDetailPage />)

    fireEvent.click(screen.getByRole("button", { name: /^Void$/ }))
    fireEvent.click(screen.getByRole("button", { name: "Void item" }))

    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ orderItemId: "item-1" })
    )
  })
})
