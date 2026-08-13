import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { GuestTokenError } from "@/lib/guest-api-client"
import GuestOrderPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "qr-token-123" }),
}))

const useGuestMenuMock = vi.fn()
const useGuestOrderMock = vi.fn()
const createGuestOrderMock = vi.fn()
const addGuestOrderItemMock = vi.fn()
const submitGuestOrderMock = vi.fn()

vi.mock("@/hooks/use-guest-order", () => ({
  useGuestMenu: (...args: unknown[]) => useGuestMenuMock(...args),
  useGuestOrder: (...args: unknown[]) => useGuestOrderMock(...args),
  useCreateGuestOrder: () => ({ mutateAsync: createGuestOrderMock }),
  useAddGuestOrderItem: () => ({ mutateAsync: addGuestOrderItemMock }),
  useSubmitGuestOrder: () => ({ mutateAsync: submitGuestOrderMock }),
}))

const MENU = {
  branchId: "b1",
  tableId: "t1",
  restaurantName: "Test Restaurant",
  branchName: "Downtown",
  tableNumber: "12",
  categories: [
    {
      id: "c1",
      name: "Mains",
      displayOrder: 0,
      items: [
        { id: "m1", name: "Burger", priceAmount: "8.99", currencyCode: "USD" },
        { id: "m2", name: "Fries", priceAmount: "3.50", currencyCode: "USD" },
      ],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  useGuestOrderMock.mockReturnValue({ data: undefined, isLoading: false, isError: false })
})

describe("GuestOrderPage", () => {
  it("renders a loading skeleton while the menu is loading", () => {
    useGuestMenuMock.mockReturnValue({ isLoading: true, isError: false, data: undefined })

    const { container } = render(<GuestOrderPage />)

    expect(container.querySelectorAll("[data-slot='skeleton']").length).toBeGreaterThan(0)
  })

  it("shows a not-found message when the QR token doesn't resolve", () => {
    useGuestMenuMock.mockReturnValue({
      isLoading: false,
      isError: true,
      error: new GuestTokenError("not_found"),
      data: undefined,
    })

    render(<GuestOrderPage />)

    expect(screen.getByText("This QR code isn't valid")).toBeInTheDocument()
  })

  it("shows a rate-limited message distinctly from a not-found one", () => {
    useGuestMenuMock.mockReturnValue({
      isLoading: false,
      isError: true,
      error: new GuestTokenError("rate_limited"),
      data: undefined,
    })

    render(<GuestOrderPage />)

    expect(screen.getByText("Too many requests")).toBeInTheDocument()
  })

  it("renders the restaurant/branch/table header and menu items", () => {
    useGuestMenuMock.mockReturnValue({ isLoading: false, isError: false, data: MENU })

    render(<GuestOrderPage />)

    expect(screen.getByText("Test Restaurant")).toBeInTheDocument()
    expect(screen.getByText("Downtown")).toBeInTheDocument()
    expect(screen.getByText("Table 12")).toBeInTheDocument()
    expect(screen.getByText("Burger")).toBeInTheDocument()
    expect(screen.getByText("Fries")).toBeInTheDocument()
  })

  it("shows an empty-menu message when there are no categories", () => {
    useGuestMenuMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { ...MENU, categories: [] },
    })

    render(<GuestOrderPage />)

    expect(screen.getByText("Nothing on the menu right now")).toBeInTheDocument()
  })

  it("adding an item reveals the sticky send-to-kitchen bar with the running count", () => {
    useGuestMenuMock.mockReturnValue({ isLoading: false, isError: false, data: MENU })

    render(<GuestOrderPage />)
    expect(screen.queryByText(/Send to kitchen/)).not.toBeInTheDocument()

    fireEvent.click(screen.getByLabelText("Add one Burger"))
    fireEvent.click(screen.getByLabelText("Add one Burger"))
    fireEvent.click(screen.getByLabelText("Add one Fries"))

    expect(screen.getByText("Send to kitchen · 3 items")).toBeInTheDocument()
  })

  it("removing an item back to zero hides the sticky bar again", () => {
    useGuestMenuMock.mockReturnValue({ isLoading: false, isError: false, data: MENU })

    render(<GuestOrderPage />)
    fireEvent.click(screen.getByLabelText("Add one Burger"))
    fireEvent.click(screen.getByLabelText("Remove one Burger"))

    expect(screen.queryByText(/Send to kitchen/)).not.toBeInTheDocument()
  })

  it("sending to the kitchen creates the order, adds each cart item, and submits", async () => {
    useGuestMenuMock.mockReturnValue({ isLoading: false, isError: false, data: MENU })
    createGuestOrderMock.mockResolvedValue({ id: "order-1" })
    addGuestOrderItemMock.mockResolvedValue({ id: "order-1" })
    submitGuestOrderMock.mockResolvedValue({ id: "order-1", status: "fired" })

    render(<GuestOrderPage />)
    fireEvent.click(screen.getByLabelText("Add one Burger"))
    fireEvent.click(await screen.findByText("Send to kitchen · 1 item"))

    await vi.waitFor(() => expect(submitGuestOrderMock).toHaveBeenCalledWith("order-1"))
    expect(addGuestOrderItemMock).toHaveBeenCalledWith({
      orderId: "order-1",
      body: { menuItemId: "m1", quantity: 1 },
    })
    expect(sessionStorage.getItem("guest-order:qr-token-123")).toBe("order-1")
  })
})
