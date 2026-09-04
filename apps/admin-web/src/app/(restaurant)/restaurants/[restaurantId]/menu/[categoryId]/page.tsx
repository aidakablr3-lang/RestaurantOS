"use client"

import * as React from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { PencilIcon, PlusIcon, UtensilsCrossedIcon } from "lucide-react"

import { MenuItemFormDialog } from "@/components/menu-item-form-dialog"
import { PermissionRestricted } from "@/components/permission-restricted"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
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
import { useMenuCategory } from "@/hooks/use-menu-categories"
import { useMenuItems } from "@/hooks/use-menu-items"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { formatMoney } from "@/lib/money"

const PAGE_SIZE = 20

export default function MenuItemsPage() {
  const params = useParams<{ restaurantId: string; categoryId: string }>()
  const { restaurantId, categoryId } = params
  const [offset, setOffset] = React.useState(0)

  const perms = usePermissionHelpers()
  const canRead = perms.hasTenantWide("menu.read")
  const canManage = perms.hasTenantWide("menu.manage")
  const enabled = !perms.isLoading && canRead

  const categoryQuery = useMenuCategory(restaurantId, categoryId, { enabled })
  const category = categoryQuery.data?.data

  const { data, isLoading, isError, error, refetch } = useMenuItems(
    categoryId,
    { offset, limit: PAGE_SIZE },
    { enabled }
  )

  const menuItems = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title={category?.name ?? "Menu items"}
        description="Items in this category. Prices and availability can be overridden per branch from an item's own page."
        actions={
          canManage ? (
            <MenuItemFormDialog
              menuCategoryId={categoryId}
              trigger={
                <Button size="sm">
                  <PlusIcon />
                  Add item
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
        /{" "}
        <Link href={`/restaurants/${restaurantId}/menu`} className="hover:underline">
          Menu
        </Link>{" "}
        / {category?.name ?? categoryId}
      </p>

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="menu items" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load menu items."}
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
      ) : menuItems.length === 0 ? (
        <EmptyState
          icon={UtensilsCrossedIcon}
          title="No menu items yet"
          description={
            canManage
              ? "Add this category's first item."
              : "No items have been added to this category yet."
          }
          action={
            canManage ? (
              <MenuItemFormDialog
                menuCategoryId={categoryId}
                trigger={
                  <Button size="sm">
                    <PlusIcon />
                    Add item
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
                <TableHead>Price</TableHead>
                <TableHead>Station</TableHead>
                <TableHead>Available</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {menuItems.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">
                    <Link
                      href={`/restaurants/${restaurantId}/menu/${categoryId}/items/${item.id}`}
                      className="hover:underline"
                    >
                      {item.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatMoney(item.priceAmount, item.currencyCode)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">
                      {item.station}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={item.isAvailable ? "secondary" : "outline"}>
                      {item.isAvailable ? "Available" : "Unavailable"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {canManage ? (
                      <MenuItemFormDialog
                        menuCategoryId={categoryId}
                        menuItem={item}
                        trigger={
                          <Button variant="ghost" size="icon" aria-label={`Edit ${item.name}`}>
                            <PencilIcon />
                          </Button>
                        }
                      />
                    ) : null}
                  </TableCell>
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
