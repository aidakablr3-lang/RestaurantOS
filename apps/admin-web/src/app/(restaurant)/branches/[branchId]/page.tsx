"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { ClockIcon, LockIcon, PencilIcon, UnlockIcon } from "lucide-react"
import { toast } from "sonner"

import { BranchStatusBadge } from "@/components/branch-status-badge"
import { BranchSubNav } from "@/components/branch-sub-nav"
import { PermissionRestricted } from "@/components/permission-restricted"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useBranch, useCloseBranch, useReopenBranch, useReplaceOperatingHours } from "@/hooks/use-branches"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { dayLabel } from "@/lib/schemas/branch"
import type { OperatingHoursEntry, OperatingHoursEntryInput } from "@/types/branch"

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 py-2 text-sm sm:grid-cols-[180px_1fr]">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium break-words">{value}</span>
    </div>
  )
}

function toTimeInputValue(value: string | null): string {
  if (!value) return ""
  return value.slice(0, 5)
}

function fromTimeInputValue(value: string): string | null {
  if (!value) return null
  return value.length === 5 ? `${value}:00` : value
}

function buildWeek(existing: OperatingHoursEntry[]): OperatingHoursEntryInput[] {
  return Array.from({ length: 7 }, (_, dayOfWeek) => {
    const found = existing.find((entry) => entry.dayOfWeek === dayOfWeek)
    return {
      dayOfWeek,
      isClosed: found?.isClosed ?? true,
      opensAt: found?.opensAt ?? null,
      closesAt: found?.closesAt ?? null,
    }
  })
}

function OperatingHoursDialog({
  branchId,
  entries,
}: {
  branchId: string
  entries: OperatingHoursEntry[]
}) {
  const [open, setOpen] = React.useState(false)
  const [week, setWeek] = React.useState<OperatingHoursEntryInput[]>(() => buildWeek(entries))
  const replaceHours = useReplaceOperatingHours(branchId)

  React.useEffect(() => {
    if (open) {
      setWeek(buildWeek(entries))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  function updateDay(dayOfWeek: number, patch: Partial<OperatingHoursEntryInput>) {
    setWeek((current) =>
      current.map((entry) => (entry.dayOfWeek === dayOfWeek ? { ...entry, ...patch } : entry))
    )
  }

  async function handleSave() {
    try {
      await replaceHours.mutateAsync({ entries: week, idempotencyKey: newIdempotencyKey() })
      toast.success("Operating hours updated.")
      setOpen(false)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to update operating hours."
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <ClockIcon />
            Edit hours
          </Button>
        }
      />
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Operating hours</DialogTitle>
        </DialogHeader>
        <div className="grid gap-2">
          {week.map((entry) => (
            <div
              key={entry.dayOfWeek}
              className="grid grid-cols-[100px_auto_1fr_1fr] items-center gap-3 text-sm"
            >
              <span className="font-medium">{dayLabel(entry.dayOfWeek)}</span>
              <label className="flex items-center gap-1.5 text-muted-foreground">
                <Checkbox
                  checked={!entry.isClosed}
                  onCheckedChange={(checked) =>
                    updateDay(entry.dayOfWeek, { isClosed: !checked })
                  }
                />
                Open
              </label>
              <input
                type="time"
                disabled={entry.isClosed}
                value={toTimeInputValue(entry.opensAt ?? null)}
                onChange={(event) =>
                  updateDay(entry.dayOfWeek, {
                    opensAt: fromTimeInputValue(event.target.value),
                  })
                }
                className="h-8 rounded-md border border-input bg-background px-2 text-sm disabled:opacity-40"
              />
              <input
                type="time"
                disabled={entry.isClosed}
                value={toTimeInputValue(entry.closesAt ?? null)}
                onChange={(event) =>
                  updateDay(entry.dayOfWeek, {
                    closesAt: fromTimeInputValue(event.target.value),
                  })
                }
                className="h-8 rounded-md border border-input bg-background px-2 text-sm disabled:opacity-40"
              />
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button onClick={handleSave} disabled={replaceHours.isPending}>
            {replaceHours.isPending ? "Saving…" : "Save hours"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function BranchDetailsPage() {
  const params = useParams<{ branchId: string }>()
  const router = useRouter()
  const branchId = params.branchId

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "branch.read")
  const canManage = perms.hasAtBranch(branchId, "branch.manage")

  const { data, isLoading, isError, error, refetch } = useBranch(branchId, {
    enabled: !perms.isLoading && canRead,
  })
  const branch = data?.data

  const closeBranch = useCloseBranch(branchId)
  const reopenBranch = useReopenBranch(branchId)

  async function handleClose() {
    try {
      await closeBranch.mutateAsync(newIdempotencyKey())
      toast.success("Branch closed.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to close branch.")
    }
  }

  async function handleReopen() {
    try {
      await reopenBranch.mutateAsync(newIdempotencyKey())
      toast.success("Branch reopened.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to reopen branch.")
    }
  }

  if (perms.isLoading || isLoading) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!canRead) {
    return <PermissionRestricted resource="this branch" />
  }

  if (isError || !branch) {
    return (
      <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">
          {error instanceof ApiError ? error.message : "Failed to load this branch."}
        </p>
        <div className="mx-auto flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
          <Button variant="ghost" onClick={() => router.push("/branches")}>
            Back to branches
          </Button>
        </div>
      </div>
    )
  }

  const address = branch.address
  const canClose = branch.status === "opened" || branch.status === "active"
  const canReopen = branch.status === "temporarily_closed"

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">{branch.name}</h1>
            <BranchStatusBadge status={branch.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            <Link href="/branches" className="hover:underline">
              Branches
            </Link>{" "}
            / {branch.name}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canManage ? (
            <Button
              variant="outline"
              render={<Link href={`/branches/${branch.id}/edit`} />}
              nativeButton={false}
            >
              <PencilIcon />
              Edit
            </Button>
          ) : null}
          {canManage && canClose ? (
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <Button variant="destructive" disabled={closeBranch.isPending}>
                    <LockIcon />
                    Close branch
                  </Button>
                }
              />
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Close this branch?</AlertDialogTitle>
                  <AlertDialogDescription>
                    {branch.name} will be marked temporarily closed until reopened.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel disabled={closeBranch.isPending}>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleClose} disabled={closeBranch.isPending}>
                    {closeBranch.isPending ? "Closing…" : "Close branch"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}
          {canManage && canReopen ? (
            <Button onClick={handleReopen} disabled={reopenBranch.isPending}>
              <UnlockIcon />
              {reopenBranch.isPending ? "Reopening…" : "Reopen branch"}
            </Button>
          ) : null}
        </div>
      </div>

      <BranchSubNav branchId={branch.id} />

      {branch.status === "temporarily_closed" || branch.status === "permanently_closed" ? (
        <div className="rounded-xl border border-muted-foreground/20 bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
          {branch.status === "temporarily_closed"
            ? "This branch is temporarily closed. Reopen it when it's ready to accept guests again."
            : "This branch is permanently closed."}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="divide-y">
            <DetailRow label="Name" value={branch.name} />
            <DetailRow label="Status" value={<BranchStatusBadge status={branch.status} />} />
            <DetailRow
              label="Address"
              value={
                address
                  ? [address.line1, address.city, address.postalCode, address.countryCode]
                      .filter(Boolean)
                      .join(", ") || "—"
                  : "Not set"
              }
            />
            <DetailRow label="Created" value={new Date(branch.createdAt).toLocaleString()} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Operating hours</CardTitle>
            {canManage ? (
              <OperatingHoursDialog branchId={branch.id} entries={branch.operatingHours} />
            ) : null}
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Day</TableHead>
                  <TableHead>Hours</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 7 }, (_, dayOfWeek) => {
                  const entry = branch.operatingHours.find((e) => e.dayOfWeek === dayOfWeek)
                  const closed = entry?.isClosed ?? true
                  return (
                    <TableRow key={dayOfWeek}>
                      <TableCell>{dayLabel(dayOfWeek)}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {closed
                          ? "Closed"
                          : `${toTimeInputValue(entry?.opensAt ?? null) || "—"} – ${
                              toTimeInputValue(entry?.closesAt ?? null) || "—"
                            }`}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
