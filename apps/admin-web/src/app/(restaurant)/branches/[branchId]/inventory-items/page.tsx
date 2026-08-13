"use client"

import * as React from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { BoxIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

import { BranchSubNav } from "@/components/branch-sub-nav"
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
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Pagination } from "@/components/ui/pagination"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useCreateInventoryItem, useInventoryCategories, useInventoryItems } from "@/hooks/use-inventory"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { type CreateInventoryItemFormValues, createInventoryItemSchema } from "@/lib/schemas/inventory-item"

const PAGE_SIZE = 20

function CreateItemDialog({ branchId, categories }: { branchId: string; categories: { id: string; name: string }[] }) {
  const [open, setOpen] = React.useState(false)
  const createItem = useCreateInventoryItem(branchId)

  const defaults: CreateInventoryItemFormValues = { inventoryCategoryId: "", name: "", unit: "" }
  const form = useForm<CreateInventoryItemFormValues>({
    resolver: zodResolver(createInventoryItemSchema),
    defaultValues: defaults,
  })
  const categoryLabels = Object.fromEntries(categories.map((category) => [category.id, category.name]))

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: CreateInventoryItemFormValues) {
    try {
      await createItem.mutateAsync({
        inventoryCategoryId: values.inventoryCategoryId,
        name: values.name,
        unit: values.unit,
        reorderPoint: values.reorderPoint !== undefined ? String(values.reorderPoint) : null,
      })
      toast.success("Inventory item created.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create this item.")
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
          <DialogTitle>Add an inventory item</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="inventoryCategoryId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Category</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={categoryLabels}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Choose a category" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {categories.map((category) => (
                        <SelectItem key={category.id} value={category.id}>
                          {category.name}
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
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Tomatoes" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="unit"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Unit</FormLabel>
                  <FormControl>
                    <Input placeholder="kg" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reorderPoint"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reorder point (optional)</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} step="0.01" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={createItem.isPending}>
                {createItem.isPending ? "Creating…" : "Create item"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function InventoryItemsPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId
  const [offset, setOffset] = React.useState(0)

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "inventory.read")
  const canManage = perms.hasAtBranch(branchId, "inventory.manage")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = useInventoryItems(branchId, { offset, limit: PAGE_SIZE }, { enabled })
  const categoriesQuery = useInventoryCategories({ enabled: enabled && canManage })
  const categories = categoriesQuery.data?.data ?? []
  const categoryNameById = new Map(categories.map((c) => [c.id, c.name]))

  const items = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Inventory"
        description="Stock levels for this branch."
        actions={canManage ? <CreateItemDialog branchId={branchId} categories={categories} /> : undefined}
      />

      <BranchSubNav branchId={branchId} />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="inventory" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load inventory items."}
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
      ) : items.length === 0 ? (
        <EmptyState
          icon={BoxIcon}
          title="No inventory items yet"
          description={
            canManage
              ? "Add an item to start tracking stock for this branch."
              : "No inventory items have been set up for this branch yet."
          }
          action={canManage ? <CreateItemDialog branchId={branchId} categories={categories} /> : undefined}
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Unit</TableHead>
                <TableHead>On hand</TableHead>
                <TableHead>Reorder point</TableHead>
                <TableHead className="w-16" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">
                    <Link href={`/branches/${branchId}/inventory-items/${item.id}`} className="hover:underline">
                      {item.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {categoryNameById.get(item.inventoryCategoryId) ?? item.inventoryCategoryId}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{item.unit}</TableCell>
                  <TableCell className="text-muted-foreground">{item.quantityOnHand}</TableCell>
                  <TableCell className="text-muted-foreground">{item.reorderPoint ?? "—"}</TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      render={<Link href={`/branches/${branchId}/inventory-items/${item.id}`} />}
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
