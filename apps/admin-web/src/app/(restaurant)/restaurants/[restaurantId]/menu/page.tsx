"use client"

import * as React from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { BookOpenIcon, PencilIcon, PlusIcon } from "lucide-react"
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Pagination } from "@/components/ui/pagination"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCreateMenuCategory, useMenuCategories, useUpdateMenuCategory } from "@/hooks/use-menu-categories"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { type MenuCategoryFormValues, menuCategorySchema } from "@/lib/schemas/menu-category"
import type { MenuCategory } from "@/types/menu-category"

const PAGE_SIZE = 20

function MenuCategoryFormDialog({
  restaurantId,
  menuCategory,
  trigger,
}: {
  restaurantId: string
  menuCategory?: MenuCategory
  trigger: React.ReactElement
}) {
  const [open, setOpen] = React.useState(false)
  const isEdit = Boolean(menuCategory)
  const createMenuCategory = useCreateMenuCategory(restaurantId)
  const updateMenuCategory = useUpdateMenuCategory(restaurantId, menuCategory?.id ?? "")
  const mutation = isEdit ? updateMenuCategory : createMenuCategory

  const form = useForm<MenuCategoryFormValues>({
    resolver: zodResolver(menuCategorySchema),
    defaultValues: {
      name: menuCategory?.name ?? "",
      displayOrder: menuCategory?.displayOrder ?? 0,
    },
  })

  function handleOpenChange(next: boolean) {
    if (next) {
      form.reset({
        name: menuCategory?.name ?? "",
        displayOrder: menuCategory?.displayOrder ?? 0,
      })
    }
    setOpen(next)
  }

  async function onSubmit(values: MenuCategoryFormValues) {
    try {
      if (isEdit) {
        await updateMenuCategory.mutateAsync(values)
        toast.success("Menu category updated.")
      } else {
        await createMenuCategory.mutateAsync({ body: values, idempotencyKey: newIdempotencyKey() })
        toast.success("Menu category created.")
      }
      setOpen(false)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to save this menu category."
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit menu category" : "Add menu category"}</DialogTitle>
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
                    <Input placeholder="Appetizers" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="displayOrder"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Display order</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} step={1} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending
                  ? isEdit
                    ? "Saving…"
                    : "Creating…"
                  : isEdit
                    ? "Save changes"
                    : "Create category"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function MenuCategoriesPage() {
  const params = useParams<{ restaurantId: string }>()
  const restaurantId = params.restaurantId
  const [offset, setOffset] = React.useState(0)

  const perms = usePermissionHelpers()
  const canRead = perms.hasTenantWide("menu.read")
  const canManage = perms.hasTenantWide("menu.manage")

  const { data, isLoading, isError, error, refetch } = useMenuCategories(
    restaurantId,
    { offset, limit: PAGE_SIZE },
    { enabled: !perms.isLoading && canRead }
  )

  const menuCategories = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Menu"
        description="Categories organize this restaurant's menu items. Menu items are shared across every branch."
        actions={
          canManage ? (
            <MenuCategoryFormDialog
              restaurantId={restaurantId}
              trigger={
                <Button size="sm">
                  <PlusIcon />
                  Add category
                </Button>
              }
            />
          ) : undefined
        }
      />

      <p className="text-sm text-muted-foreground">
        <Link href={`/restaurants/${restaurantId}`} className="hover:underline">
          Restaurant
        </Link>{" "}
        / Menu
      </p>

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="the menu" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load menu categories."}
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
      ) : menuCategories.length === 0 ? (
        <EmptyState
          icon={BookOpenIcon}
          title="No menu categories yet"
          description={
            canManage
              ? "Add a category like Appetizers or Mains to start building the menu."
              : "No menu categories have been set up for this restaurant yet."
          }
          action={
            canManage ? (
              <MenuCategoryFormDialog
                restaurantId={restaurantId}
                trigger={
                  <Button size="sm">
                    <PlusIcon />
                    Add category
                  </Button>
                }
              />
            ) : undefined
          }
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Display order</TableHead>
                {canManage ? <TableHead className="w-20" /> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {menuCategories.map((category) => (
                <TableRow key={category.id}>
                  <TableCell className="font-medium">
                    <Link
                      href={`/restaurants/${restaurantId}/menu/${category.id}`}
                      className="hover:underline"
                    >
                      {category.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{category.displayOrder}</TableCell>
                  {canManage ? (
                    <TableCell>
                      <MenuCategoryFormDialog
                        restaurantId={restaurantId}
                        menuCategory={category}
                        trigger={
                          <Button variant="ghost" size="icon" aria-label={`Edit ${category.name}`}>
                            <PencilIcon />
                          </Button>
                        }
                      />
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {meta && meta.total > 0 ? (
        <Pagination
          offset={meta.offset}
          limit={meta.limit}
          total={meta.total}
          onOffsetChange={setOffset}
        />
      ) : null}
    </div>
  )
}
