"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PlusIcon, TruckIcon } from "lucide-react"
import { toast } from "sonner"

import { BranchSubNav } from "@/components/branch-sub-nav"
import { PermissionRestricted } from "@/components/permission-restricted"
import { PurchaseOrderStatusBadge } from "@/components/purchase-order-status-badge"
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
import { useCreatePurchaseOrder, usePurchaseOrders } from "@/hooks/use-purchase-orders"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useSuppliers } from "@/hooks/use-suppliers"
import { ApiError } from "@/lib/api-client"
import { type CreatePurchaseOrderFormValues, createPurchaseOrderSchema } from "@/lib/schemas/purchase-order"

const PAGE_SIZE = 20

function NewPurchaseOrderDialog({ branchId, suppliers }: { branchId: string; suppliers: { id: string; name: string }[] }) {
  const [open, setOpen] = React.useState(false)
  const router = useRouter()
  const createPO = useCreatePurchaseOrder(branchId)

  const form = useForm<CreatePurchaseOrderFormValues>({
    resolver: zodResolver(createPurchaseOrderSchema),
    defaultValues: { supplierId: "" },
  })
  const supplierLabels = Object.fromEntries(suppliers.map((supplier) => [supplier.id, supplier.name]))

  function handleOpenChange(next: boolean) {
    if (next) form.reset({ supplierId: "" })
    setOpen(next)
  }

  async function onSubmit(values: CreatePurchaseOrderFormValues) {
    try {
      const result = await createPO.mutateAsync(values)
      toast.success("Purchase order created.")
      setOpen(false)
      router.push(`/branches/${branchId}/purchase-orders/${result.data.id}`)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create this purchase order.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            New purchase order
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New purchase order</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="supplierId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Supplier</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={supplierLabels}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Choose a supplier" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {suppliers.map((supplier) => (
                        <SelectItem key={supplier.id} value={supplier.id}>
                          {supplier.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={createPO.isPending}>
                {createPO.isPending ? "Creating…" : "Create draft"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function PurchaseOrdersPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId
  const [offset, setOffset] = React.useState(0)

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "purchasing.read")
  const canManage = perms.hasAtBranch(branchId, "purchasing.manage")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = usePurchaseOrders(branchId, { offset, limit: PAGE_SIZE }, { enabled })
  const suppliersQuery = useSuppliers({ offset: 0, limit: 100 }, { enabled: enabled && canManage })
  const suppliers = suppliersQuery.data?.data ?? []
  const supplierNameById = new Map(suppliers.map((s) => [s.id, s.name]))

  const purchaseOrders = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Purchase orders"
        description="Draft, send, and receive purchase orders for this branch."
        actions={canManage ? <NewPurchaseOrderDialog branchId={branchId} suppliers={suppliers} /> : undefined}
      />

      <BranchSubNav branchId={branchId} />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="purchase orders" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load purchase orders."}
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
      ) : purchaseOrders.length === 0 ? (
        <EmptyState
          icon={TruckIcon}
          title="No purchase orders yet"
          description={
            canManage
              ? "Create a purchase order to start restocking from a supplier."
              : "No purchase orders have been created for this branch yet."
          }
          action={canManage ? <NewPurchaseOrderDialog branchId={branchId} suppliers={suppliers} /> : undefined}
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Supplier</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="w-16" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {purchaseOrders.map((po) => (
                <TableRow key={po.id}>
                  <TableCell className="font-medium">{supplierNameById.get(po.supplierId) ?? po.supplierId}</TableCell>
                  <TableCell>
                    <PurchaseOrderStatusBadge status={po.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{new Date(po.createdAt).toLocaleDateString()}</TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      render={<Link href={`/branches/${branchId}/purchase-orders/${po.id}`} />}
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
