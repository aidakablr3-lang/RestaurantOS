"use client"

import * as React from "react"
import Link from "next/link"
import { StoreIcon } from "lucide-react"

import { BranchStatusBadge } from "@/components/branch-status-badge"
import { PermissionRestricted } from "@/components/permission-restricted"
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
import { useBranches } from "@/hooks/use-branches"
import { usePermissionHelpers } from "@/hooks/use-permissions"

const PAGE_SIZE = 20

export default function BranchesPage() {
  const [offset, setOffset] = React.useState(0)
  const perms = usePermissionHelpers()
  const canRead = perms.hasAnywhere("branch.read")

  const { data, isLoading, isError, error, refetch } = useBranches(
    { offset, limit: PAGE_SIZE },
    { enabled: !perms.isLoading && canRead }
  )

  const branches = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Branches"
        description="Every branch you have access to, across all restaurants."
      />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="branches" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : "Failed to load branches."}
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
      ) : branches.length === 0 ? (
        <EmptyState
          icon={StoreIcon}
          title="No branches yet"
          description="Add a branch from inside a restaurant to see it listed here."
          action={
            <Button render={<Link href="/restaurants" />} nativeButton={false}>
              Go to restaurants
            </Button>
          }
        />
      ) : (
        // No City/Country column here: GET /api/v1/branches never
        // populates address (a backend gap, see docs/DEVELOPMENT.md's
        // Restaurant Platform frontend section) -- showing it would
        // read as "no address set" when the branch may well have one.
        // The branch detail page uses GET /branches/{id}, which does
        // return it correctly.
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {branches.map((branch) => (
                <TableRow key={branch.id}>
                  <TableCell>
                    <Link
                      href={`/branches/${branch.id}`}
                      className="font-medium hover:underline"
                    >
                      {branch.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <BranchStatusBadge status={branch.status} />
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
