"use client"

import * as React from "react"
import { useParams, useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { FlameIcon, PlusIcon, ReceiptIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import { OrderItemLineStatusBadge, OrderStatusBadge } from "@/components/order-status-badge"
import { PermissionRestricted } from "@/components/permission-restricted"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useGenerateBill } from "@/hooks/use-bills"
import { useBranch } from "@/hooks/use-branches"
import { useRestaurantMenuItems } from "@/hooks/use-menu-items"
import { useAddOrderItem, useCloseOrder, useFireOrder, useOrder, useVoidOrder } from "@/hooks/use-orders"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { type AddOrderItemFormValues, addOrderItemSchema } from "@/lib/schemas/order"
import type { MenuItem } from "@/types/menu-item"

function AddItemDialog({
  branchId,
  orderId,
  menuItems,
  menuItemsLoading,
}: {
  branchId: string
  orderId: string
  menuItems: MenuItem[]
  menuItemsLoading: boolean
}) {
  const [open, setOpen] = React.useState(false)
  const addItem = useAddOrderItem(branchId, orderId)
  const available = menuItems.filter((item) => item.isAvailable)
  const itemLabels = React.useMemo(
    () => Object.fromEntries(available.map((item) => [item.id, item.name])),
    [available]
  )

  const form = useForm<AddOrderItemFormValues>({
    resolver: zodResolver(addOrderItemSchema),
    defaultValues: { menuItemId: "", quantity: 1 },
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset({ menuItemId: "", quantity: 1 })
    setOpen(next)
  }

  async function onSubmit(values: AddOrderItemFormValues) {
    try {
      await addItem.mutateAsync({
        body: { menuItemId: values.menuItemId, quantity: values.quantity },
        idempotencyKey: newIdempotencyKey(),
      })
      toast.success("Item added.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to add this item.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            Add item
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add an item</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="menuItemId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Menu item</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={itemLabels}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder={menuItemsLoading ? "Loading…" : "Choose an item"} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {available.map((item) => (
                        <SelectItem key={item.id} value={item.id}>
                          {item.name} — {item.priceAmount} {item.currencyCode}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="quantity"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Quantity</FormLabel>
                  <FormControl>
                    <Input type="number" min={1} step={1} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={addItem.isPending}>
                {addItem.isPending ? "Adding…" : "Add item"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function OrderDetailPage() {
  const params = useParams<{ branchId: string; orderId: string }>()
  const router = useRouter()
  const branchId = params.branchId
  const orderId = params.orderId

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "order.read")
  const canManage = perms.hasAtBranch(branchId, "order.manage")
  const canBill = perms.hasAtBranch(branchId, "billing.manage")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = useOrder(branchId, orderId, { enabled })
  const order = data?.data
  const branchQuery = useBranch(branchId, { enabled })
  const restaurantId = branchQuery.data?.data.restaurantId
  const menuItemsQuery = useRestaurantMenuItems(restaurantId ?? "", { enabled: enabled && Boolean(restaurantId) })
  const menuItemNameById = new Map(menuItemsQuery.data.map((item) => [item.id, item.name]))

  const fireOrder = useFireOrder(branchId, orderId)
  const closeOrder = useCloseOrder(branchId, orderId)
  const voidOrder = useVoidOrder(branchId, orderId)
  const generateBill = useGenerateBill()

  async function handleFire() {
    try {
      await fireOrder.mutateAsync(newIdempotencyKey())
      toast.success("Order fired to the kitchen.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to fire this order.")
    }
  }

  async function handleClose() {
    try {
      await closeOrder.mutateAsync(newIdempotencyKey())
      toast.success("Order closed.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to close this order.")
    }
  }

  async function handleVoid() {
    try {
      await voidOrder.mutateAsync(newIdempotencyKey())
      toast.success("Order voided.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to void this order.")
    }
  }

  async function handleGenerateBill() {
    try {
      const result = await generateBill.mutateAsync(orderId)
      toast.success("Bill generated.")
      router.push(`/bills/${result.data.id}`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to generate a bill for this order.")
    }
  }

  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title={order ? `Order · ${new Date(order.openedAt).toLocaleString()}` : "Order"}
        description="Add items, fire to the kitchen, and close out once paid."
      />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="this order" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load this order."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : loading || !order ? (
        <div className="grid gap-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : (
        <>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Summary</CardTitle>
              <OrderStatusBadge status={order.status} />
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-4">
              <div>
                <p className="text-xs text-muted-foreground">Subtotal</p>
                <p className="font-medium">
                  {order.subtotalAmount} {order.currencyCode}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Tax</p>
                <p className="font-medium">
                  {order.taxAmount} {order.currencyCode}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Total</p>
                <p className="font-medium">
                  {order.totalAmount} {order.currencyCode}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Table</p>
                <p className="font-medium">{order.tableId ?? "—"}</p>
              </div>
            </CardContent>
          </Card>

          {canManage ? (
            <div className="flex flex-wrap items-center gap-2">
              {order.status === "open" ? (
                <>
                  <AddItemDialog
                    branchId={branchId}
                    orderId={orderId}
                    menuItems={menuItemsQuery.data}
                    menuItemsLoading={menuItemsQuery.isLoading}
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={order.items.length === 0 || fireOrder.isPending}
                    onClick={handleFire}
                  >
                    <FlameIcon />
                    {fireOrder.isPending ? "Firing…" : "Fire to kitchen"}
                  </Button>
                </>
              ) : null}
              {(order.status === "fired" || order.status === "served") && canBill ? (
                <Button size="sm" variant="secondary" disabled={generateBill.isPending} onClick={handleGenerateBill}>
                  <ReceiptIcon />
                  {generateBill.isPending ? "Generating…" : "Generate bill"}
                </Button>
              ) : null}
              {order.status === "fired" || order.status === "served" || order.status === "billed" ? (
                <Button size="sm" variant="outline" disabled={closeOrder.isPending} onClick={handleClose}>
                  {closeOrder.isPending ? "Closing…" : "Close order"}
                </Button>
              ) : null}
              {order.status === "open" || order.status === "fired" ? (
                <AlertDialog>
                  <AlertDialogTrigger
                    render={
                      <Button size="sm" variant="destructive" disabled={voidOrder.isPending}>
                        <XIcon />
                        Void order
                      </Button>
                    }
                  />
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Void this order?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This cannot be undone -- the order moves to a terminal, unbillable state.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel disabled={voidOrder.isPending}>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={handleVoid} disabled={voidOrder.isPending}>
                        {voidOrder.isPending ? "Voiding…" : "Void order"}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              ) : null}
            </div>
          ) : null}

          <div className="min-w-0 rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead>Quantity</TableHead>
                  <TableHead>Unit price</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {order.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="py-8 text-center text-muted-foreground">
                      No items added yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  order.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">
                        {menuItemNameById.get(item.menuItemId) ?? item.menuItemId}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{item.quantity}</TableCell>
                      <TableCell className="text-muted-foreground">{item.unitPriceAmount}</TableCell>
                      <TableCell>
                        <OrderItemLineStatusBadge status={item.lineStatus} />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}
