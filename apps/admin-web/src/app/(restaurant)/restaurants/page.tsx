"use client"

import * as React from "react"
import Link from "next/link"
import { PlusIcon, StoreIcon } from "lucide-react"

import { PermissionRestricted } from "@/components/permission-restricted"
import { RestaurantStatusBadge } from "@/components/restaurant-status-badge"
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
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useRestaurants } from "@/hooks/use-restaurants"

const PAGE_SIZE = 20

export default function RestaurantsPage() {
  const [offset, setOffset] = React.useState(0)
  const perms = usePermissionHelpers()
  const canRead = perms.hasTenantWide("restaurant.read")
  const canManage = perms.hasTenantWide("restaurant.manage")

  const { data, isLoading, isError, error, refetch } = useRestaurants(
    { offset, limit: PAGE_SIZE },
    { enabled: !perms.isLoading && canRead }
  )

  const restaurants = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Restaurants"
        description="The restaurant concepts your tenant operates."
        actions={
          canManage ? (
            <Button render={<Link href="/restaurants/new" />} nativeButton={false}>
              <PlusIcon />
              New restaurant
            </Button>
          ) : undefined
        }
      />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="restaurants" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : "Failed to load restaurants."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : loading ? (
        <div className="grid gap-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : restaurants.length === 0 ? (
        <EmptyState
          icon={StoreIcon}
          title="No restaurants yet"
          description="Create your first restaurant to start adding branches, menus, and reservations."
          action={
            canManage ? (
              <Button render={<Link href="/restaurants/new" />} nativeButton={false}>
                <PlusIcon />
                New restaurant
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Display name</TableHead>
                <TableHead>Legal name</TableHead>
                <TableHead>Currency</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {restaurants.map((restaurant) => (
                <TableRow key={restaurant.id}>
                  <TableCell>
                    <Link
                      href={`/restaurants/${restaurant.id}`}
                      className="font-medium hover:underline"
                    >
                      {restaurant.displayName}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {restaurant.legalName}
                  </TableCell>
                  <TableCell>{restaurant.defaultCurrencyCode}</TableCell>
                  <TableCell>
                    <RestaurantStatusBadge status={restaurant.status} />
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
