"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { ClipboardListIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

import { BranchSubNav } from "@/components/branch-sub-nav"
import { OrderStatusBadge } from "@/components/order-status-badge"
import { PermissionRestricted } from "@/components/permission-restricted"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { PageHeader } from "@/components/ui/page-header"
import { Pagination } from "@/components/ui/pagination"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useCreateOrder, useOrders } from "@/hooks/use-orders"
import { useTables } from "@/hooks/use-tables"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { type CreateOrderFormValues, createOrderSchema } from "@/lib/schemas/order"

const PAGE_SIZE = 20
const NO_TABLE = "none"

const ORDER_SOURCE_LABEL: Record<string, string> = {
  pos: "POS (dine-in)",
  qr: "QR (guest self-order)",
  delivery: "Delivery",
  takeaway: "Takeaway",
}

function NewOrderDialog({ branchId, tableIds }: { branchId: string; tableIds: { id: string; tableNumber: string }[] }) {
  const [open, setOpen] = React.useState(false)
  const router = useRouter()
  const createOrder = useCreateOrder(branchId)

  const form = useForm<CreateOrderFormValues>({
    resolver: zodResolver(createOrderSchema),
    defaultValues: { orderSource: "pos", tableId: NO_TABLE },
  })
  const tableLabels = {
    [NO_TABLE]: "No table assigned",
    ...Object.fromEntries(tableIds.map((table) => [table.id, `Table ${table.tableNumber}`])),
  }

  function handleOpenChange(next: boolean) {
    if (next) form.reset({ orderSource: "pos", tableId: NO_TABLE })
    setOpen(next)
  }

  async function onSubmit(values: CreateOrderFormValues) {
    try {
      const result = await createOrder.mutateAsync({
        body: {
          orderSource: values.orderSource,
          tableId: !values.tableId || values.tableId === NO_TABLE ? null : values.tableId,
        },
        idempotencyKey: newIdempotencyKey(),
      })
      toast.success("Order opened.")
      setOpen(false)
      router.push(`/branches/${branchId}/orders/${result.data.id}`)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to open this order.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            New order
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Open a new order</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="orderSource"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Order source</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={ORDER_SOURCE_LABEL}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {Object.entries(ORDER_SOURCE_LABEL).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
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
              name="tableId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Table (optional)</FormLabel>
                  <Select value={field.value || NO_TABLE} onValueChange={field.onChange} items={tableLabels}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NO_TABLE}>No table assigned</SelectItem>
                      {tableIds.map((table) => (
                        <SelectItem key={table.id} value={table.id}>
                          Table {table.tableNumber}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={createOrder.isPending}>
                {createOrder.isPending ? "Opening…" : "Open order"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function OrdersPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId
  const [offset, setOffset] = React.useState(0)

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "order.read")
  const canManage = perms.hasAtBranch(branchId, "order.manage")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = useOrders(
    branchId,
    { offset, limit: PAGE_SIZE },
    { enabled }
  )
  const tablesQuery = useTables(branchId, { offset: 0, limit: 100 }, { enabled: enabled && canManage })
  const tables = tablesQuery.data?.data ?? []

  const orders = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Orders"
        description="Dine-in, delivery, and takeaway orders for this branch."
        actions={canManage ? <NewOrderDialog branchId={branchId} tableIds={tables} /> : undefined}
      />

      <BranchSubNav branchId={branchId} />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="orders" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load orders."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : loading ? (
        <div className="grid gap-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <EmptyState
          icon={ClipboardListIcon}
          title="No orders yet"
          description={
            canManage
              ? "Open an order to start taking items for this branch."
              : "No orders have been opened for this branch yet."
          }
          action={canManage ? <NewOrderDialog branchId={branchId} tableIds={tables} /> : undefined}
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Opened</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Items</TableHead>
                <TableHead>Total</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((order) => (
                <TableRow key={order.id}>
                  <TableCell className="font-medium">
                    {new Date(order.openedAt).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {ORDER_SOURCE_LABEL[order.orderSource] ?? order.orderSource}
                  </TableCell>
                  <TableCell>
                    <OrderStatusBadge status={order.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{order.items.length}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {order.totalAmount} {order.currencyCode}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      render={<Link href={`/branches/${branchId}/orders/${order.id}`} />}
                      nativeButton={false}
                    >
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {meta && meta.total > 0 ? (
        <Pagination offset={meta.offset} limit={meta.limit} total={meta.total} onOffsetChange={setOffset} />
      ) : null}
    </div>
  )
}
