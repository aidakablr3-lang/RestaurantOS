"use client"

/**
 * Counter POS -- single-screen, tap-to-add, no-dialog order entry for a
 * fast walk-up/takeaway sale. The existing order flow (New order dialog
 * -> Add item dialog per item -> Fire -> Generate bill -> Record
 * payment dialog -> Print) is ~12 clicks and 4 screens for a one-item
 * sale; this screen gets a one-item cash sale to 3 taps: tile -> Pay ->
 * Print. No table picker -- this is specifically the no-table counter
 * path (`orderSource: "pos"`, `tableId: null`), the same default the
 * "New order" dialog on the orders list page already uses.
 *
 * **Disclosed, NOT fixed here:** every ``MenuItem.station`` is either
 * "kitchen" or "bar" (restaurant/domain/entities/menu_item.py) -- there
 * is no "no station" value. "Pay" below auto-fires the order before
 * billing (never skips firing -- billing without firing would risk a
 * real food/bar item silently never reaching the kitchen), which means
 * even a pure retail item like a bottled drink still creates a real
 * ``KitchenTicket`` that sits on the Kitchen Display page until someone
 * bumps it. The clean fix is a future ``MenuItemStation.NONE``/
 * ``RETAIL`` value that ``_station_routing.py`` skips entirely when
 * fanning fired items out into tickets -- not built here, flagged so
 * the KDS clutter this causes doesn't get forgotten.
 *
 * **Pay and Print are independent actions, not one pipeline.** Print
 * only requires a bill to exist -- it doesn't call Pay, and Pay doesn't
 * call Print. Today the only thing that creates a bill is Pay's own
 * auto-fire -> generate-bill -> record-payment sequence, so the
 * effective default is pay-then-print. If real counter behavior turns
 * out to be print-a-quote-before-payment instead, that only means
 * something else (a lightweight "generate bill" step) needs to run
 * before Print becomes available -- not a redesign of either button.
 */

import * as React from "react"
import { useParams } from "next/navigation"
import { PrinterIcon, WalletIcon } from "lucide-react"
import { toast } from "sonner"

import { BillPrintView } from "@/app/(restaurant)/bills/[billId]/bill-print-view"
import { BranchSubNav } from "@/components/branch-sub-nav"
import { PermissionRestricted } from "@/components/permission-restricted"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Skeleton } from "@/components/ui/skeleton"
import { useBill, useGenerateBill } from "@/hooks/use-bills"
import { useBranch } from "@/hooks/use-branches"
import { useMenuCategories } from "@/hooks/use-menu-categories"
import { useRestaurantMenuItems } from "@/hooks/use-menu-items"
import { useCreateOrder } from "@/hooks/use-orders"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import {
  usePosAddOrderItem,
  usePosFireOrder,
  usePosRecordPayment,
  usePosUpdateOrderItemQuantity,
  usePosVoidOrderItem,
} from "@/hooks/use-pos"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { formatMoney } from "@/lib/money"
import type { MenuItem } from "@/types/menu-item"
import type { Order, OrderItem } from "@/types/order"
import type { TenderType } from "@/types/payment"

const TENDER_OPTIONS: { value: TenderType; label: string }[] = [
  { value: "cash", label: "Cash" },
  { value: "card", label: "Card" },
  { value: "wallet", label: "Wallet" },
]

function findEditableLine(order: Order, menuItemId: string): OrderItem | undefined {
  return order.items.find((item) => item.menuItemId === menuItemId && item.lineStatus === "added")
}

export default function CounterPosPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId

  const perms = usePermissionHelpers()
  const canManage = perms.hasAtBranch(branchId, "order.manage")
  const canBill = perms.hasAtBranch(branchId, "billing.manage")
  const enabled = !perms.isLoading && canManage && canBill

  const branchQuery = useBranch(branchId, { enabled })
  const restaurantId = branchQuery.data?.data.restaurantId

  const menuItemsQuery = useRestaurantMenuItems(restaurantId ?? "", {
    enabled: enabled && Boolean(restaurantId),
  })
  const categoriesQuery = useMenuCategories(
    restaurantId ?? "",
    { offset: 0, limit: 100 },
    { enabled: enabled && Boolean(restaurantId) }
  )
  const categories = categoriesQuery.data?.data ?? []

  const [order, setOrder] = React.useState<Order | null>(null)
  const [billId, setBillId] = React.useState<string | null>(null)
  const [search, setSearch] = React.useState("")
  const [tenderType, setTenderType] = React.useState<TenderType>("cash")

  const billQuery = useBill(billId ?? undefined, { enabled: Boolean(billId) })
  const bill = billQuery.data?.data

  const createOrder = useCreateOrder(branchId)
  const addItem = usePosAddOrderItem(branchId)
  const updateQuantity = usePosUpdateOrderItemQuantity(branchId)
  const voidItem = usePosVoidOrderItem(branchId)
  const fireOrderMut = usePosFireOrder(branchId)
  const generateBill = useGenerateBill()
  const recordPaymentMut = usePosRecordPayment()

  const busy =
    createOrder.isPending ||
    addItem.isPending ||
    updateQuantity.isPending ||
    voidItem.isPending ||
    fireOrderMut.isPending ||
    generateBill.isPending ||
    recordPaymentMut.isPending

  async function handleTileTap(menuItem: MenuItem) {
    try {
      let currentOrder = order
      if (!currentOrder) {
        const created = await createOrder.mutateAsync({
          body: { orderSource: "pos", tableId: null },
          idempotencyKey: newIdempotencyKey(),
        })
        currentOrder = created.data
        setOrder(currentOrder)
      }

      const existingLine = findEditableLine(currentOrder, menuItem.id)
      const updated = existingLine
        ? await updateQuantity.mutateAsync({
            orderId: currentOrder.id,
            orderItemId: existingLine.id,
            body: { quantity: existingLine.quantity + 1 },
          })
        : await addItem.mutateAsync({
            orderId: currentOrder.id,
            body: { menuItemId: menuItem.id, quantity: 1 },
            idempotencyKey: newIdempotencyKey(),
          })
      setOrder(updated.data)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to add this item.")
    }
  }

  async function handleIncrement(line: OrderItem) {
    if (!order) return
    try {
      const updated = await updateQuantity.mutateAsync({
        orderId: order.id,
        orderItemId: line.id,
        body: { quantity: line.quantity + 1 },
      })
      setOrder(updated.data)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to update this item.")
    }
  }

  async function handleDecrement(line: OrderItem) {
    if (!order) return
    try {
      const updated =
        line.quantity > 1
          ? await updateQuantity.mutateAsync({
              orderId: order.id,
              orderItemId: line.id,
              body: { quantity: line.quantity - 1 },
            })
          : await voidItem.mutateAsync({
              orderId: order.id,
              orderItemId: line.id,
              idempotencyKey: newIdempotencyKey(),
            })
      setOrder(updated.data)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to update this item.")
    }
  }

  async function handlePay() {
    if (!order) return
    try {
      let currentOrder = order
      if (currentOrder.status === "open") {
        const fired = await fireOrderMut.mutateAsync({
          orderId: currentOrder.id,
          idempotencyKey: newIdempotencyKey(),
        })
        currentOrder = fired.data
        setOrder(currentOrder)
      }

      let currentBillId = billId
      let amountDue = bill?.amountDue
      if (!currentBillId) {
        const generated = await generateBill.mutateAsync(currentOrder.id)
        currentBillId = generated.data.id
        amountDue = generated.data.amountDue
        setBillId(currentBillId)
      }
      if (!currentBillId || !amountDue) {
        toast.error("Bill total not ready yet -- try Pay again in a moment.")
        return
      }

      await recordPaymentMut.mutateAsync({
        billId: currentBillId,
        body: { tenderType, amount: amountDue },
      })
      toast.success("Payment recorded.")
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to record payment.")
    }
  }

  function handleNewSale() {
    setOrder(null)
    setBillId(null)
    setSearch("")
    setTenderType("cash")
  }

  const menuItemNameById = new Map(menuItemsQuery.data.map((item) => [item.id, item.name]))

  const availableItems = menuItemsQuery.data.filter((item) => item.isAvailable)
  const searchLower = search.trim().toLowerCase()
  const filteredItems = searchLower
    ? availableItems.filter((item) => item.name.toLowerCase().includes(searchLower))
    : availableItems

  const itemsByCategory = new Map<string, MenuItem[]>()
  for (const item of filteredItems) {
    const bucket = itemsByCategory.get(item.menuCategoryId)
    if (bucket) bucket.push(item)
    else itemsByCategory.set(item.menuCategoryId, [item])
  }
  const orderedCategories = [...categories]
    .filter((c) => itemsByCategory.has(c.id))
    .sort((a, b) => a.displayOrder - b.displayOrder)
  for (const bucket of itemsByCategory.values()) {
    bucket.sort((a, b) => a.displayOrder - b.displayOrder)
  }

  const visibleLines = order?.items.filter((item) => item.lineStatus !== "voided") ?? []
  const hasItems = visibleLines.length > 0
  const isPaid = bill?.status === "closed"
  const loadingMenu = menuItemsQuery.isLoading || categoriesQuery.isLoading || branchQuery.isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Counter"
        description="Tap items to add them, then Pay and Print. No table needed."
      />

      <BranchSubNav branchId={branchId} />

      {!perms.isLoading && !(canManage && canBill) ? (
        <PermissionRestricted resource="the counter" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
          <div className="grid gap-4">
            <Input
              placeholder="Search menu…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-12 text-base"
            />

            {loadingMenu ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {Array.from({ length: 9 }).map((_, index) => (
                  <Skeleton key={index} className="h-16 w-full" />
                ))}
              </div>
            ) : filteredItems.length === 0 ? (
              <EmptyState
                icon={WalletIcon}
                title="No matching items"
                description={search ? "Try a different search." : "No menu items are available."}
              />
            ) : searchLower ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {filteredItems.map((item) => (
                  <MenuTile key={item.id} item={item} disabled={busy} onTap={handleTileTap} />
                ))}
              </div>
            ) : (
              <div className="grid gap-5">
                {orderedCategories.map((category) => (
                  <div key={category.id} className="grid gap-2">
                    <h3 className="text-sm font-semibold text-muted-foreground">
                      {category.name}
                    </h3>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                      {(itemsByCategory.get(category.id) ?? []).map((item) => (
                        <MenuTile
                          key={item.id}
                          item={item}
                          disabled={busy}
                          onTap={handleTileTap}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex h-fit flex-col gap-3 rounded-xl border p-4 lg:sticky lg:top-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold">Order</h2>
              {order ? (
                <Button variant="ghost" size="sm" onClick={handleNewSale} disabled={busy}>
                  New sale
                </Button>
              ) : null}
            </div>

            {!hasItems ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Tap a menu item to start an order.
              </p>
            ) : (
              <ul className="grid max-h-[45vh] gap-2 overflow-y-auto">
                {visibleLines.map((line) => (
                  <OrderLine
                    key={line.id}
                    line={line}
                    name={menuItemNameById.get(line.menuItemId) ?? line.menuItemId}
                    currencyCode={order?.currencyCode ?? "INR"}
                    editable={line.lineStatus === "added" && !busy}
                    onIncrement={() => handleIncrement(line)}
                    onDecrement={() => handleDecrement(line)}
                  />
                ))}
              </ul>
            )}

            <div className="grid gap-1 border-t pt-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Subtotal</span>
                <span className="font-medium">
                  {order ? formatMoney(order.subtotalAmount, order.currencyCode) : "—"}
                </span>
              </div>
              {bill ? (
                <>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Tax</span>
                    <span className="font-medium">
                      {formatMoney(bill.taxAmount, order?.currencyCode ?? "INR")}
                    </span>
                  </div>
                  <div className="flex justify-between text-base font-semibold">
                    <span>Total</span>
                    <span>
                      {formatMoney(
                        (Number(bill.subtotalAmount) + Number(bill.taxAmount)).toFixed(2),
                        order?.currencyCode ?? "INR"
                      )}
                    </span>
                  </div>
                </>
              ) : (
                <p className="text-xs text-muted-foreground">Tax and total are set at payment.</p>
              )}
            </div>

            <div className="grid grid-cols-3 gap-2">
              {TENDER_OPTIONS.map((option) => (
                <Button
                  key={option.value}
                  type="button"
                  size="sm"
                  variant={tenderType === option.value ? "default" : "outline"}
                  disabled={busy || isPaid}
                  onClick={() => setTenderType(option.value)}
                  className="h-11"
                >
                  {option.label}
                </Button>
              ))}
            </div>

            <Button
              className="h-16 text-lg"
              disabled={!hasItems || busy || isPaid}
              onClick={handlePay}
            >
              {isPaid ? "Paid" : busy ? "Working…" : "Pay"}
            </Button>
            <Button
              variant="outline"
              className="h-16 text-lg"
              disabled={!billId}
              onClick={() => window.print()}
            >
              <PrinterIcon className="size-5" />
              Print
            </Button>
          </div>
        </div>
      )}

      {bill ? <BillPrintView bill={bill} /> : null}
    </div>
  )
}

function MenuTile({
  item,
  disabled,
  onTap,
}: {
  item: MenuItem
  disabled: boolean
  onTap: (item: MenuItem) => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onTap(item)}
      className="flex min-h-16 flex-col items-start justify-center gap-0.5 rounded-lg border bg-background px-3 py-2 text-left transition-colors hover:bg-muted active:translate-y-px disabled:pointer-events-none disabled:opacity-50"
    >
      <span className="text-sm font-medium leading-tight">{item.name}</span>
      <span className="text-xs text-muted-foreground">
        {formatMoney(item.priceAmount, item.currencyCode)}
      </span>
    </button>
  )
}

function OrderLine({
  line,
  name,
  currencyCode,
  editable,
  onIncrement,
  onDecrement,
}: {
  line: OrderItem
  name: string
  currencyCode: string
  editable: boolean
  onIncrement: () => void
  onDecrement: () => void
}) {
  return (
    <li className="grid grid-cols-[1fr_auto] items-center gap-2 rounded-md border px-2 py-1.5">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{name}</p>
        <p className="text-xs text-muted-foreground">
          {formatMoney(line.unitPriceAmount, currencyCode)} ×{" "}
          {formatMoney(
            (Number(line.unitPriceAmount) * line.quantity).toFixed(2),
            currencyCode
          )}
        </p>
      </div>
      {editable ? (
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="size-9"
            onClick={onDecrement}
            aria-label="Decrease quantity"
          >
            −
          </Button>
          <span className="w-6 text-center text-sm font-semibold">{line.quantity}</span>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="size-9"
            onClick={onIncrement}
            aria-label="Increase quantity"
          >
            +
          </Button>
        </div>
      ) : (
        <span className="px-2 text-sm text-muted-foreground">×{line.quantity}</span>
      )}
    </li>
  )
}
