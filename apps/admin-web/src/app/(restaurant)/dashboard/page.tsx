"use client"

import Link from "next/link"
import { CalendarClockIcon, StoreIcon, UtensilsCrossedIcon } from "lucide-react"

import { PageHeader } from "@/components/ui/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { useBranches } from "@/hooks/use-branches"
import { useRestaurants } from "@/hooks/use-restaurants"

function StatCard({
  title,
  value,
  isLoading,
  href,
}: {
  title: string
  value: number | null
  isLoading: boolean
  href: string
}) {
  return (
    <Link href={href}>
      <Card className="transition-colors hover:border-foreground/20">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-8 w-12" />
          ) : (
            <p className="text-2xl font-semibold">{value ?? "—"}</p>
          )}
        </CardContent>
      </Card>
    </Link>
  )
}

export default function DashboardPage() {
  const restaurants = useRestaurants({ offset: 0, limit: 1 })
  const branches = useBranches({ offset: 0, limit: 1 })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="An overview of the restaurants and branches you have access to."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          title="Restaurants"
          value={restaurants.data?.meta?.total ?? null}
          isLoading={restaurants.isLoading}
          href="/restaurants"
        />
        <StatCard
          title="Branches"
          value={branches.data?.meta?.total ?? null}
          isLoading={branches.isLoading}
          href="/branches"
        />
        <Card className="opacity-60">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Today&apos;s reservations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Unavailable — select a branch under Reservations to view its list.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <StoreIcon className="size-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">Restaurants &amp; branches</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Set up restaurants, add branches, and manage addresses and operating hours.
            </p>
            <Button
              size="sm"
              variant="outline"
              render={<Link href="/restaurants" />}
              nativeButton={false}
            >
              Manage restaurants
            </Button>
          </CardContent>
        </Card>
        <Card className="opacity-60">
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <CalendarClockIcon className="size-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">Reservations</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Coming soon.</p>
          </CardContent>
        </Card>
        <Card className="opacity-60">
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <UtensilsCrossedIcon className="size-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">Menu</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Coming soon.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
