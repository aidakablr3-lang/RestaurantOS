import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import ReservationsPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ branchId: "b1" }),
  usePathname: () => "/branches/b1/reservations",
}))

const usePermissionHelpersMock = vi.fn()
vi.mock("@/hooks/use-permissions", () => ({
  usePermissionHelpers: () => usePermissionHelpersMock(),
}))

const useReservationsMock = vi.fn()
vi.mock("@/hooks/use-reservations", () => ({
  useReservations: (...args: unknown[]) => useReservationsMock(...args),
  useCreateReservation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateReservation: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

describe("ReservationsPage permission gating", () => {
  it("shows a restricted state for a user without reservation.read at this branch", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms())
    useReservationsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<ReservationsPage />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
    expect(screen.queryByText("Add reservation")).not.toBeInTheDocument()
  })

  it("hides the Add reservation action for a read-only user", () => {
    usePermissionHelpersMock.mockReturnValue(
      mockPerms({ hasAtBranch: (_id, p) => p === "reservation.read" })
    )
    useReservationsMock.mockReturnValue({
      data: { data: [], meta: { total: 0, offset: 0, limit: 20 } },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<ReservationsPage />)

    expect(screen.getByText("No reservations yet")).toBeInTheDocument()
    expect(screen.queryByText("Add reservation")).not.toBeInTheDocument()
  })

  it("shows the Add reservation action and status-transition buttons for a user with reservation.manage", () => {
    usePermissionHelpersMock.mockReturnValue(mockPerms({ hasAtBranch: () => true }))
    useReservationsMock.mockReturnValue({
      data: {
        data: [
          {
            id: "res1",
            tenantId: "t1",
            branchId: "b1",
            tableId: null,
            customerId: null,
            partySize: 2,
            requestedAt: "2026-01-01T19:00:00Z",
            status: "requested",
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

    render(<ReservationsPage />)

    expect(screen.getAllByText("Add reservation").length).toBeGreaterThan(0)
    expect(screen.getByText("Confirm")).toBeInTheDocument()
    expect(screen.getByText("Cancel")).toBeInTheDocument()
  })
})
