"use client"

import * as React from "react"
import Link from "next/link"
import { PlusIcon } from "lucide-react"

import { TenantStatusBadge } from "@/components/tenant-status-badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useTenants } from "@/hooks/use-tenants"
import type { TenantStatus } from "@/lib/api-types"

const PAGE_SIZE = 20
const STATUS_OPTIONS: Array<TenantStatus | "ALL"> = [
  "ALL",
  "provisioning",
  "active",
  "suspended",
  "migrating",
  "offboarded",
]

export default function TenantListPage() {
  const [offset, setOffset] = React.useState(0)
  const [status, setStatus] = React.useState<TenantStatus | "ALL">("ALL")

  const { data, isLoading, isError, error, refetch, isFetching } = useTenants({
    offset,
    limit: PAGE_SIZE,
    status: status === "ALL" ? undefined : status,
  })

  const tenants = data?.data ?? []
  const meta = data?.meta

  function handleStatusChange(value: string | null) {
    if (!value) return
    setStatus(value as TenantStatus | "ALL")
    setOffset(0)
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Tenants</h1>
          <p className="text-sm text-muted-foreground">
            Manage tenant accounts on the platform.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={status} onValueChange={handleStatusChange}>
            <SelectTrigger aria-label="Filter by status" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((option) => (
                <SelectItem key={option} value={option} className="capitalize">
                  {option === "ALL" ? "All statuses" : option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button render={<Link href="/tenants/new" />} nativeButton={false}>
            <PlusIcon />
            New Tenant
          </Button>
        </div>
      </div>

      {isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof Error
              ? error.message
              : "Failed to load tenants."}
          </p>
          <Button
            variant="outline"
            className="mx-auto"
            onClick={() => refetch()}
          >
            Retry
          </Button>
        </div>
      ) : isLoading ? (
        <div className="grid gap-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : tenants.length === 0 ? (
        <div className="grid gap-2 rounded-xl border border-dashed p-10 text-center">
          <p className="text-sm font-medium">No tenants found</p>
          <p className="text-sm text-muted-foreground">
            {status === "ALL"
              ? "Onboard your first tenant to get started."
              : `No tenants with status ${status}.`}
          </p>
        </div>
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Display name</TableHead>
                <TableHead>Legal name</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Currency</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tenants.map((tenant) => (
                <TableRow key={tenant.id} className="cursor-pointer">
                  <TableCell>
                    <Link
                      href={`/tenants/${tenant.id}`}
                      className="font-medium hover:underline"
                    >
                      {tenant.displayName}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {tenant.legalName}
                  </TableCell>
                  <TableCell>{tenant.tenantTier}</TableCell>
                  <TableCell>{tenant.defaultCurrencyCode}</TableCell>
                  <TableCell>
                    <TenantStatusBadge status={tenant.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {meta && meta.total > PAGE_SIZE ? (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Showing {meta.offset + 1}
            {"–"}
            {Math.min(meta.offset + meta.limit, meta.total)} of {meta.total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0 || isFetching}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + PAGE_SIZE >= meta.total || isFetching}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
