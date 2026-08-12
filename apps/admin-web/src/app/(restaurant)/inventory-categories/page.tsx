"use client"

import * as React from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { BoxIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

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
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useCreateInventoryCategory, useInventoryCategories } from "@/hooks/use-inventory"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import {
  type CreateInventoryCategoryFormValues,
  createInventoryCategorySchema,
} from "@/lib/schemas/inventory-category"

function CreateCategoryDialog() {
  const [open, setOpen] = React.useState(false)
  const createCategory = useCreateInventoryCategory()

  const form = useForm<CreateInventoryCategoryFormValues>({
    resolver: zodResolver(createInventoryCategorySchema),
    defaultValues: { name: "" },
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset({ name: "" })
    setOpen(next)
  }

  async function onSubmit(values: CreateInventoryCategoryFormValues) {
    try {
      await createCategory.mutateAsync(values)
      toast.success("Category created.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create this category.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            Add category
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add an inventory category</DialogTitle>
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
                    <Input placeholder="Produce" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={createCategory.isPending}>
                {createCategory.isPending ? "Creating…" : "Create category"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function InventoryCategoriesPage() {
  const perms = usePermissionHelpers()
  const canRead = perms.hasTenantWide("inventory.read")
  const canManage = perms.hasTenantWide("inventory.manage")

  const { data, isLoading, isError, error, refetch } = useInventoryCategories({
    enabled: !perms.isLoading && canRead,
  })

  const categories = data?.data ?? []
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Inventory categories"
        description="Groupings like Produce or Dry Goods, shared across every branch in this tenant."
        actions={canManage ? <CreateCategoryDialog /> : undefined}
      />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="inventory categories" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load inventory categories."}
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
      ) : categories.length === 0 ? (
        <EmptyState
          icon={BoxIcon}
          title="No inventory categories yet"
          description={
            canManage
              ? "Add a category like Produce or Dry Goods, then create items under it."
              : "No inventory categories have been set up for this tenant yet."
          }
          action={canManage ? <CreateCategoryDialog /> : undefined}
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {categories.map((category) => (
                <TableRow key={category.id}>
                  <TableCell className="font-medium">{category.name}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(category.createdAt).toLocaleDateString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
