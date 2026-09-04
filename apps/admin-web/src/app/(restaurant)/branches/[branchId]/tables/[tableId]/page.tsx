"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { CopyIcon, PrinterIcon, QrCodeIcon, RefreshCwIcon } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { toast } from "sonner"

import { QRCodeStatusBadge } from "@/components/qr-code-status-badge"
import { PermissionRestricted } from "@/components/permission-restricted"
import { TableStatusBadge } from "@/components/table-status-badge"
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
import { EmptyState } from "@/components/ui/empty-state"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table as TableComponent,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useBranch } from "@/hooks/use-branches"
import { useGenerateQRCode, useQRCodes } from "@/hooks/use-qr-codes"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useRestaurant } from "@/hooks/use-restaurants"
import { useTableZone } from "@/hooks/use-table-zones"
import { useChangeTableStatus, useTable } from "@/hooks/use-tables"
import { ApiError } from "@/lib/api-client"
import { guestOrderUrl } from "@/lib/guest-url"
import { newIdempotencyKey } from "@/lib/idempotency"
import type { TableStatus } from "@/types/table"

import { QRCodePrintView } from "./qr-code-print-view"

const STATUS_OPTIONS: TableStatus[] = ["available", "occupied", "reserved", "cleaning"]

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 py-2 text-sm sm:grid-cols-[180px_1fr]">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium break-words">{value}</span>
    </div>
  )
}

async function copyToken(token: string) {
  try {
    await navigator.clipboard.writeText(token)
    toast.success("Token copied to clipboard.")
  } catch {
    toast.error("Couldn't copy the token. Copy it manually instead.")
  }
}

export default function TableDetailPage() {
  const params = useParams<{ branchId: string; tableId: string }>()
  const router = useRouter()
  const { branchId, tableId } = params

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "table.read")
  const canManage = perms.hasAtBranch(branchId, "table.manage")
  const enabled = !perms.isLoading && canRead

  const tableQuery = useTable(branchId, tableId, { enabled })
  const table = tableQuery.data?.data

  const zoneQuery = useTableZone(branchId, table?.tableZoneId, {
    enabled: enabled && Boolean(table),
  })
  const zone = zoneQuery.data?.data

  const qrCodesQuery = useQRCodes(tableId, { enabled })
  const qrCodes = qrCodesQuery.data?.data ?? []
  const activeCode = qrCodes.find((code) => code.status === "active")

  const branchQuery = useBranch(branchId)
  const branch = branchQuery.data?.data
  const restaurantQuery = useRestaurant(branch?.restaurantId)
  const restaurant = restaurantQuery.data?.data

  const guestUrl = activeCode ? guestOrderUrl(activeCode.token) : null

  const changeStatus = useChangeTableStatus(branchId, tableId)
  const generateQR = useGenerateQRCode(tableId)

  async function handleStatusChange(next: string | null) {
    if (!next) return
    const status = next as TableStatus
    if (!table || status === table.status) return
    try {
      await changeStatus.mutateAsync({ status, idempotencyKey: newIdempotencyKey() })
      toast.success(`Status updated to ${status}.`)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to update table status.")
    }
  }

  async function handleGenerate() {
    try {
      await generateQR.mutateAsync(newIdempotencyKey())
      toast.success(activeCode ? "New QR code generated." : "QR code generated.")
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to generate a QR code.")
    }
  }

  if (perms.isLoading || tableQuery.isLoading) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!canRead) {
    return <PermissionRestricted resource="this table" />
  }

  if (tableQuery.isError || !table) {
    return (
      <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">
          {tableQuery.error instanceof ApiError
            ? tableQuery.error.message
            : "Failed to load this table."}
        </p>
        <div className="mx-auto flex gap-2">
          <Button variant="outline" onClick={() => tableQuery.refetch()}>
            Retry
          </Button>
          <Button variant="ghost" onClick={() => router.push(`/branches/${branchId}/tables`)}>
            Back to tables
          </Button>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="grid gap-6 print:hidden">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold">Table {table.tableNumber}</h1>
              <TableStatusBadge status={table.status} />
            </div>
            <p className="text-sm text-muted-foreground">
              <Link href={`/branches/${branchId}/tables`} className="hover:underline">
                Tables
              </Link>{" "}
              / Table {table.tableNumber}
            </p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
            </CardHeader>
            <CardContent className="divide-y">
              <DetailRow label="Table number" value={table.tableNumber} />
              <DetailRow label="Dining area" value={zone?.name ?? "—"} />
              <DetailRow label="Capacity" value={table.capacity} />
              <DetailRow
                label="Status"
                value={
                  canManage ? (
                    <Select
                      value={table.status}
                      onValueChange={handleStatusChange}
                      disabled={changeStatus.isPending}
                    >
                      <SelectTrigger size="sm" aria-label="Change table status">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {STATUS_OPTIONS.map((status) => (
                          <SelectItem key={status} value={status}>
                            {status[0]?.toUpperCase() + status.slice(1)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <TableStatusBadge status={table.status} />
                  )
                }
              />
              <DetailRow label="Created" value={new Date(table.createdAt).toLocaleString()} />
            </CardContent>
          </Card>

          <Card className="min-w-0">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>QR codes</CardTitle>
              {canManage ? (
                activeCode ? (
                  <AlertDialog>
                    <AlertDialogTrigger
                      render={
                        <Button variant="outline" size="sm" disabled={generateQR.isPending}>
                          <RefreshCwIcon />
                          Regenerate
                        </Button>
                      }
                    />
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Generate a new QR code?</AlertDialogTitle>
                        <AlertDialogDescription>
                          This creates a new active code for Table {table.tableNumber} and
                          immediately revokes the current one. Any signage or printed code using
                          the old QR code will stop working.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel disabled={generateQR.isPending}>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleGenerate} disabled={generateQR.isPending}>
                          {generateQR.isPending ? "Generating…" : "Generate new code"}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                ) : (
                  <Button size="sm" onClick={handleGenerate} disabled={generateQR.isPending}>
                    <QrCodeIcon />
                    {generateQR.isPending ? "Generating…" : "Generate QR code"}
                  </Button>
                )
              ) : null}
            </CardHeader>
            <CardContent>
              {activeCode && guestUrl ? (
                <div className="mb-6 flex flex-col items-center gap-3 border-b pb-6 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex flex-col items-center gap-2 sm:items-start">
                    <QRCodeSVG value={guestUrl} size={144} />
                    <p className="max-w-64 text-center text-xs break-all text-muted-foreground sm:text-left">
                      {guestUrl}
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => window.print()}>
                    <PrinterIcon />
                    Print
                  </Button>
                </div>
              ) : null}
              {qrCodesQuery.isLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : qrCodesQuery.isError ? (
                <div className="grid gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
                  <p className="text-sm text-destructive">
                    {qrCodesQuery.error instanceof ApiError
                      ? qrCodesQuery.error.message
                      : "Failed to load QR codes."}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mx-auto"
                    onClick={() => qrCodesQuery.refetch()}
                  >
                    Retry
                  </Button>
                </div>
              ) : qrCodes.length === 0 ? (
                <EmptyState
                  icon={QrCodeIcon}
                  title="No QR codes yet"
                  description={
                    canManage
                      ? "Generate a QR code so guests can access this table."
                      : "No QR code has been generated for this table yet."
                  }
                />
              ) : (
                <TableComponent>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Token</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {qrCodes
                      .slice()
                      .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
                      .map((code) => (
                        <TableRow key={code.id}>
                          <TableCell>
                            <div className="flex items-center gap-1.5">
                              <span className="max-w-40 truncate font-mono text-xs">
                                {code.token}
                              </span>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="size-6"
                                aria-label="Copy token"
                                onClick={() => copyToken(code.token)}
                              >
                                <CopyIcon className="size-3.5" />
                              </Button>
                            </div>
                          </TableCell>
                          <TableCell>
                            <QRCodeStatusBadge status={code.status} />
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {new Date(code.createdAt).toLocaleString()}
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </TableComponent>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
      {activeCode && guestUrl && restaurant ? (
        <QRCodePrintView
          url={guestUrl}
          tableNumber={table.tableNumber}
          restaurantName={restaurant.displayName}
        />
      ) : null}
    </>
  )
}
