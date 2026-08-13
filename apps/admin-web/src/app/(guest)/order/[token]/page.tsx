"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { AlertTriangle, Loader2, Minus, Plus, ShoppingCart } from "lucide-react"
import { toast } from "sonner"

import { ApiError } from "@/lib/api-client"
import { GuestTokenError } from "@/lib/guest-api-client"
import {
  useAddGuestOrderItem,
  useCreateGuestOrder,
  useGuestMenu,
  useGuestOrder,
  useSubmitGuestOrder,
} from "@/hooks/use-guest-order"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Skeleton } from "@/components/ui/skeleton"
import type { OrderItemLineStatus } from "@/types/order"

function sessionKey(token: string) {
  return `guest-order:${token}`
}

const LINE_STATUS_LABEL: Record<OrderItemLineStatus, string> = {
  added: "Sending to kitchen",
  fired: "In the kitchen",
  ready: "Ready",
  served: "Served",
  voided: "Removed",
}

const LINE_STATUS_VARIANT: Record<OrderItemLineStatus, "secondary" | "default" | "outline"> = {
  added: "secondary",
  fired: "default",
  ready: "default",
  served: "outline",
  voided: "outline",
}

export default function GuestOrderPage() {
  const { token } = useParams<{ token: string }>()
  const [cart, setCart] = useState<Record<string, number>>({})
  const [orderId, setOrderId] = useState<string | null>(null)
  const [placing, setPlacing] = useState(false)

  useEffect(() => {
    setOrderId(sessionStorage.getItem(sessionKey(token)))
  }, [token])

  const menuQuery = useGuestMenu(token)
  const orderQuery = useGuestOrder(token, orderId ?? undefined)
  const createOrder = useCreateGuestOrder(token)
  const addItem = useAddGuestOrderItem(token)
  const submitOrder = useSubmitGuestOrder(token)

  function setQuantity(menuItemId: string, quantity: number) {
    setCart((prev) => {
      if (quantity <= 0) {
        const next = { ...prev }
        delete next[menuItemId]
        return next
      }
      return { ...prev, [menuItemId]: quantity }
    })
  }

  const cartCount = Object.values(cart).reduce((sum, qty) => sum + qty, 0)
  const menu = menuQuery.data

  async function handleSendToKitchen() {
    if (!menu || cartCount === 0) return
    setPlacing(true)
    try {
      let activeOrderId = orderId
      if (!activeOrderId) {
        const order = await createOrder.mutateAsync()
        activeOrderId = order.id
        setOrderId(order.id)
        sessionStorage.setItem(sessionKey(token), order.id)
      }

      for (const [menuItemId, quantity] of Object.entries(cart)) {
        await addItem.mutateAsync({ orderId: activeOrderId, body: { menuItemId, quantity } })
      }

      await submitOrder.mutateAsync(activeOrderId)
      setCart({})
      toast.success("Sent to the kitchen!")
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : "Something went wrong sending your order. Please try again."
      )
    } finally {
      setPlacing(false)
    }
  }

  if (menuQuery.isLoading) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-md flex-col gap-4 p-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
        <div className="mt-4 flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  if (menuQuery.isError) {
    const error = menuQuery.error
    const isRateLimited = error instanceof GuestTokenError && error.kind === "rate_limited"
    return (
      <div className="mx-auto flex min-h-dvh max-w-md items-center p-4">
        <EmptyState
          icon={AlertTriangle}
          title={isRateLimited ? "Too many requests" : "This QR code isn't valid"}
          description={
            error instanceof Error
              ? error.message
              : "Please ask a staff member for help."
          }
        />
      </div>
    )
  }

  if (!menu) return null

  const showOrderStatus = Boolean(orderId) && Boolean(orderQuery.data)

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col pb-28">
      <header className="border-b border-border px-4 py-4">
        <p className="text-sm text-muted-foreground">{menu.restaurantName}</p>
        <h1 className="text-lg font-semibold text-foreground">{menu.branchName}</h1>
        <Badge variant="outline" className="mt-1">
          Table {menu.tableNumber}
        </Badge>
      </header>

      {showOrderStatus && orderQuery.data && (
        <section className="border-b border-border bg-muted/40 px-4 py-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Your order</h2>
            <Badge>{orderQuery.data.status}</Badge>
          </div>
          <ul className="flex flex-col gap-2">
            {orderQuery.data.items
              .filter((item) => item.lineStatus !== "voided")
              .map((item) => {
                const menuItem = menu.categories
                  .flatMap((c) => c.items)
                  .find((i) => i.id === item.menuItemId)
                return (
                  <li key={item.id} className="flex items-center justify-between text-sm">
                    <span className="text-foreground">
                      {item.quantity}× {menuItem?.name ?? "Item"}
                    </span>
                    <Badge variant={LINE_STATUS_VARIANT[item.lineStatus]}>
                      {LINE_STATUS_LABEL[item.lineStatus]}
                    </Badge>
                  </li>
                )
              })}
          </ul>
          <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-sm font-medium text-foreground">
            <span>Total</span>
            <span>
              {orderQuery.data.totalAmount} {orderQuery.data.currencyCode}
            </span>
          </div>
        </section>
      )}

      <main className="flex flex-1 flex-col gap-6 px-4 py-4">
        {menu.categories.length === 0 && (
          <EmptyState
            icon={ShoppingCart}
            title="Nothing on the menu right now"
            description="Please ask a staff member for assistance."
          />
        )}
        {menu.categories.map((category) => (
          <section key={category.id}>
            <h2 className="mb-2 text-base font-semibold text-foreground">{category.name}</h2>
            <div className="flex flex-col gap-3">
              {category.items.map((item) => {
                const quantity = cart[item.id] ?? 0
                return (
                  <div
                    key={item.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-border p-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground">{item.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {item.priceAmount} {item.currencyCode}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="icon-sm"
                        disabled={quantity === 0}
                        onClick={() => setQuantity(item.id, quantity - 1)}
                        aria-label={`Remove one ${item.name}`}
                      >
                        <Minus />
                      </Button>
                      <span className="w-4 text-center text-sm font-medium tabular-nums">
                        {quantity}
                      </span>
                      <Button
                        type="button"
                        variant="outline"
                        size="icon-sm"
                        onClick={() => setQuantity(item.id, quantity + 1)}
                        aria-label={`Add one ${item.name}`}
                      >
                        <Plus />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>
        ))}
      </main>

      {cartCount > 0 && (
        <div className="fixed inset-x-0 bottom-0 mx-auto max-w-md border-t border-border bg-background p-4">
          <Button className="w-full" onClick={handleSendToKitchen} disabled={placing}>
            {placing ? (
              <Loader2 className="animate-spin" />
            ) : (
              <ShoppingCart />
            )}
            Send to kitchen · {cartCount} item{cartCount === 1 ? "" : "s"}
          </Button>
        </div>
      )}
    </div>
  )
}
