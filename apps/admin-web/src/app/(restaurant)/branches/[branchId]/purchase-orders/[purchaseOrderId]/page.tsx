"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PackageCheckIcon, PlusIcon, SendIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

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
import { PermissionRestricted } from "@/components/permission-restricted"
import { PurchaseOrderStatusBadge } from "@/components/purchase-order-status-badge"
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
import { useInventoryItems } from "@/hooks/use-inventory"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import {
  useAddPurchaseOrderItem,
  useCancelPurchaseOrder,
  useConfirmGoodsReceipt,
  usePurchaseOrder,
  useSendPurchaseOrder,
} from "@/hooks/use-purchase-orders"
import { ApiError } from "@/lib/api-client"
import {
  type AddPurchaseOrderItemFormValues,
  addPurchaseOrderItemSchema,
} from "@/lib/schemas/purchase-order"

function AddItemDialog({
  branchId,
  purchaseOrderId,
  inventoryItems,
}: {
  branchId: string
  purchaseOrderId: string
  inventoryItems: { id: string; name: string; unit: string }[]
}) {
  const [open, setOpen] = React.useState(false)
  const addItem = useAddPurchaseOrderItem(branchId, purchaseOrderId)

  const defaults: AddPurchaseOrderItemFormValues = { inventoryItemId: "", quantityOrdered: 1 }
  const form = useForm<AddPurchaseOrderItemFormValues>({
    resolver: zodResolver(addPurchaseOrderItemSchema),
    defaultValues: defaults,
  })
  const inventoryItemLabels = Object.fromEntries(
    inventoryItems.map((item) => [item.id, `${item.name} (${item.unit})`])
  )

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: AddPurchaseOrderItemFormValues) {
    try {
      await addItem.mutateAsync({
        inventoryItemId: values.inventoryItemId,
        quantityOrdered: String(values.quantityOrdered),
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
          <DialogTitle>Add a line item</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="inventoryItemId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Inventory item</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={inventoryItemLabels}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Choose an item" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {inventoryItems.map((item) => (
                        <SelectItem key={item.id} value={item.id}>
                          {item.name} ({item.unit})
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
              name="quantityOrdered"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Quantity ordered</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} step="0.01" {...field} />
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

function ConfirmReceiptDialog({
  branchId,
  purchaseOrderId,
  items,
  itemNameById,
}: {
  branchId: string
  purchaseOrderId: string
  items: { id: string; inventoryItemId: string; quantityOrdered: string; quantityReceived: string }[]
  itemNameById: Map<string, string>
}) {
  const [open, setOpen] = React.useState(false)
  const [quantities, setQuantities] = React.useState<Record<string, string>>({})
  const confirmReceipt = useConfirmGoodsReceipt(branchId, purchaseOrderId)

  function handleOpenChange(next: boolean) {
    if (next) setQuantities({})
    setOpen(next)
  }

  async function onConfirm() {
    const lines = Object.entries(quantities)
      .filter(([, value]) => value && Number(value) > 0)
      .map(([purchaseOrderItemId, value]) => ({ purchaseOrderItemId, quantityReceived: value }))

    if (lines.length === 0) {
      toast.error("Enter a received quantity for at least one line.")
      return
    }

    try {
      const result = await confirmReceipt.mutateAsync({ lines })
      toast.success(
        result.data.hasDiscrepancy ? "Receipt confirmed with a discrepancy flagged." : "Receipt confirmed."
      )
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to confirm this receipt.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PackageCheckIcon />
            Confirm receipt
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm goods receipt</DialogTitle>
        </DialogHeader>
        <div className="grid gap-3">
          {items.map((item) => (
            <div key={item.id} className="grid grid-cols-[1fr_auto] items-center gap-3">
              <div>
                <p className="text-sm font-medium">{itemNameById.get(item.inventoryItemId) ?? item.inventoryItemId}</p>
                <p className="text-xs text-muted-foreground">
                  Ordered {item.quantityOrdered}, received so far {item.quantityReceived}
                </p>
              </div>
              <Input
                type="number"
                min={0}
                step="0.01"
                className="w-28"
                placeholder="0"
                value={quantities[item.id] ?? ""}
                onChange={(event) => setQuantities((prev) => ({ ...prev, [item.id]: event.target.value }))}
              />
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button onClick={onConfirm} disabled={confirmReceipt.isPending}>
            {confirmReceipt.isPending ? "Confirming…" : "Confirm receipt"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function PurchaseOrderDetailPage() {
  const params = useParams<{ branchId: string; purchaseOrderId: string }>()
  const branchId = params.branchId
  const purchaseOrderId = params.purchaseOrderId

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "purchasing.read")
  const canManage = perms.hasAtBranch(branchId, "purchasing.manage")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = usePurchaseOrder(branchId, purchaseOrderId, { enabled })
  const po = data?.data
  const inventoryItemsQuery = useInventoryItems(branchId, { offset: 0, limit: 100 }, { enabled: enabled && canManage })
  const inventoryItems = inventoryItemsQuery.data?.data ?? []
  const inventoryItemNameById = new Map(inventoryItems.map((item) => [item.id, item.name]))

  const sendPO = useSendPurchaseOrder(branchId, purchaseOrderId)
  const cancelPO = useCancelPurchaseOrder(branchId, purchaseOrderId)

  async function handleSend() {
    try {
      await sendPO.mutateAsync()
      toast.success("Purchase order sent.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to send this purchase order.")
    }
  }

  async function handleCancel() {
    try {
      await cancelPO.mutateAsync()
      toast.success("Purchase order canceled.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to cancel this purchase order.")
    }
  }

  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader title="Purchase order" description="Add items, send to the supplier, and confirm receipts." />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="this purchase order" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load this purchase order."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : loading || !po ? (
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
              <PurchaseOrderStatusBadge status={po.status} />
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Created {new Date(po.createdAt).toLocaleString()}.
              </p>
            </CardContent>
          </Card>

          {canManage ? (
            <div className="flex flex-wrap items-center gap-2">
              {po.status === "draft" ? (
                <>
                  <AddItemDialog branchId={branchId} purchaseOrderId={purchaseOrderId} inventoryItems={inventoryItems} />
                  <Button size="sm" variant="secondary" disabled={po.items.length === 0 || sendPO.isPending} onClick={handleSend}>
                    <SendIcon />
                    {sendPO.isPending ? "Sending…" : "Send to supplier"}
                  </Button>
                </>
              ) : null}
              {po.status === "sent" || po.status === "partially_received" ? (
                <ConfirmReceiptDialog
                  branchId={branchId}
                  purchaseOrderId={purchaseOrderId}
                  items={po.items}
                  itemNameById={inventoryItemNameById}
                />
              ) : null}
              {po.status === "draft" || po.status === "sent" ? (
                <AlertDialog>
                  <AlertDialogTrigger
                    render={
                      <Button size="sm" variant="destructive" disabled={cancelPO.isPending}>
                        <XIcon />
                        Cancel
                      </Button>
                    }
                  />
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Cancel this purchase order?</AlertDialogTitle>
                      <AlertDialogDescription>This cannot be undone.</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel disabled={cancelPO.isPending}>Keep it</AlertDialogCancel>
                      <AlertDialogAction onClick={handleCancel} disabled={cancelPO.isPending}>
                        {cancelPO.isPending ? "Canceling…" : "Cancel purchase order"}
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
                  <TableHead>Ordered</TableHead>
                  <TableHead>Received</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {po.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="py-8 text-center text-muted-foreground">
                      No items added yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  po.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">
                        {inventoryItemNameById.get(item.inventoryItemId) ?? item.inventoryItemId}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{item.quantityOrdered}</TableCell>
                      <TableCell className="text-muted-foreground">{item.quantityReceived}</TableCell>
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
