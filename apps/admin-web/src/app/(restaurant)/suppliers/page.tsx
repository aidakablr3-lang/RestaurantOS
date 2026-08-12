"use client"

import * as React from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PencilIcon, PlusIcon, TruckIcon } from "lucide-react"
import { toast } from "sonner"

import { PermissionRestricted } from "@/components/permission-restricted"
import { SupplierStatusBadge } from "@/components/supplier-status-badge"
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
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Pagination } from "@/components/ui/pagination"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useCreateSupplier, useSuppliers, useUpdateSupplier } from "@/hooks/use-suppliers"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { type CreateSupplierFormValues, createSupplierSchema } from "@/lib/schemas/supplier"
import { type UpdateSupplierFormValues, updateSupplierSchema } from "@/lib/schemas/supplier"
import type { Supplier } from "@/types/supplier"

const PAGE_SIZE = 20

const SUPPLIER_STATUS_LABEL: Record<string, string> = {
  active: "Active",
  inactive: "Inactive",
}

function CreateSupplierDialog() {
  const [open, setOpen] = React.useState(false)
  const createSupplier = useCreateSupplier()

  const form = useForm<CreateSupplierFormValues>({
    resolver: zodResolver(createSupplierSchema),
    defaultValues: { name: "" },
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset({ name: "" })
    setOpen(next)
  }

  async function onSubmit(values: CreateSupplierFormValues) {
    try {
      await createSupplier.mutateAsync(values)
      toast.success("Supplier created.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create this supplier.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            Add supplier
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a supplier</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Fresh Foods Co" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={createSupplier.isPending}>
                {createSupplier.isPending ? "Creating…" : "Create supplier"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function EditSupplierDialog({ supplier }: { supplier: Supplier }) {
  const [open, setOpen] = React.useState(false)
  const updateSupplier = useUpdateSupplier(supplier.id)

  const defaults: UpdateSupplierFormValues = { name: supplier.name, status: supplier.status }
  const form = useForm<UpdateSupplierFormValues>({
    resolver: zodResolver(updateSupplierSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: UpdateSupplierFormValues) {
    try {
      await updateSupplier.mutateAsync(values)
      toast.success("Supplier updated.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to update this supplier.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={<Button variant="ghost" size="icon" aria-label={`Edit ${supplier.name}`}><PencilIcon /></Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit supplier</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Status</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={SUPPLIER_STATUS_LABEL}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={updateSupplier.isPending}>
                {updateSupplier.isPending ? "Saving…" : "Save changes"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function SuppliersPage() {
  const [offset, setOffset] = React.useState(0)
  const perms = usePermissionHelpers()
  const canRead = perms.hasTenantWide("purchasing.read")
  const canManage = perms.hasTenantWide("purchasing.manage")

  const { data, isLoading, isError, error, refetch } = useSuppliers(
    { offset, limit: PAGE_SIZE },
    { enabled: !perms.isLoading && canRead }
  )

  const suppliers = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Suppliers"
        description="Suppliers you order inventory from, shared across every branch in this tenant."
        actions={canManage ? <CreateSupplierDialog /> : undefined}
      />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="suppliers" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load suppliers."}
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
      ) : suppliers.length === 0 ? (
        <EmptyState
          icon={TruckIcon}
          title="No suppliers yet"
          description={
            canManage
              ? "Add a supplier, then create purchase orders against it."
              : "No suppliers have been set up for this tenant yet."
          }
          action={canManage ? <CreateSupplierDialog /> : undefined}
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                {canManage ? <TableHead className="w-16" /> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {suppliers.map((supplier) => (
                <TableRow key={supplier.id}>
                  <TableCell className="font-medium">{supplier.name}</TableCell>
                  <TableCell>
                    <SupplierStatusBadge status={supplier.status} />
                  </TableCell>
                  {canManage ? (
                    <TableCell>
                      <EditSupplierDialog supplier={supplier} />
                    </TableCell>
                  ) : null}
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
