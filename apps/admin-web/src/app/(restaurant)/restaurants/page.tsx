"use client"

import * as React from "react"
import Link from "next/link"
import { PlusIcon, StoreIcon } from "lucide-react"

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
import { useRestaurants } from "@/hooks/use-restaurants"

const PAGE_SIZE = 20

export default function RestaurantsPage() {
  const [offset, setOffset] = React.useState(0)
  const { data, isLoading, isError, error, refetch } = useRestaurants({
    offset,
    limit: PAGE_SIZE,
  })

  const restaurants = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Restaurants"
        description="The restaurant concepts your tenant operates."
        actions={
          <Button render={<Link href="/restaurants/new" />} nativeButton={false}>
            <PlusIcon />
            New restaurant
          </Button>
        }
      />

      {isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : "Failed to load restaurants."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : isLoading ? (
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
            <Button render={<Link href="/restaurants/new" />} nativeButton={false}>
              <PlusIcon />
              New restaurant
            </Button>
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
