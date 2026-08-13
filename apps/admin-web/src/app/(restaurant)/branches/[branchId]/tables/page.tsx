"use client"

import * as React from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { ArmchairIcon, PencilIcon, PlusIcon, QrCodeIcon } from "lucide-react"
import { toast } from "sonner"

import { BranchSubNav } from "@/components/branch-sub-nav"
import { PermissionRestricted } from "@/components/permission-restricted"
import { TableStatusBadge } from "@/components/table-status-badge"
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
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useTableZones } from "@/hooks/use-table-zones"
import { useChangeTableStatus, useCreateTable, useTables, useUpdateTable } from "@/hooks/use-tables"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { type TableFormValues, tableSchema } from "@/lib/schemas/table"
import type { Table, TableStatus } from "@/types/table"
import type { TableZone } from "@/types/table-zone"

const PAGE_SIZE = 20
const STATUS_OPTIONS: TableStatus[] = ["available", "occupied", "reserved", "cleaning"]

function TableFormDialog({
  branchId,
  zones,
  table,
  trigger,
}: {
  branchId: string
  zones: TableZone[]
  table?: Table
  trigger: React.ReactElement
}) {
  const [open, setOpen] = React.useState(false)
  const isEdit = Boolean(table)
  const createTable = useCreateTable(branchId)
  const updateTable = useUpdateTable(branchId, table?.id ?? "")
  const mutation = isEdit ? updateTable : createTable

  const form = useForm<TableFormValues>({
    resolver: zodResolver(tableSchema),
    defaultValues: {
      tableZoneId: table?.tableZoneId ?? "",
      tableNumber: table?.tableNumber ?? "",
      capacity: table?.capacity ?? 2,
    },
  })

  function handleOpenChange(next: boolean) {
    if (next) {
      form.reset({
        tableZoneId: table?.tableZoneId ?? "",
        tableNumber: table?.tableNumber ?? "",
        capacity: table?.capacity ?? 2,
      })
    }
    setOpen(next)
  }

  async function onSubmit(values: TableFormValues) {
    try {
      if (isEdit) {
        await updateTable.mutateAsync(values)
        toast.success("Table updated.")
      } else {
        await createTable.mutateAsync({ body: values, idempotencyKey: newIdempotencyKey() })
        toast.success("Table created.")
      }
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to save this table.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit table" : "Add table"}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="tableZoneId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Dining area</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Choose a dining area" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {zones.map((zone) => (
                        <SelectItem key={zone.id} value={zone.id}>
                          {zone.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="tableNumber"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Table number</FormLabel>
                  <FormControl>
                    <Input placeholder="12" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="capacity"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Capacity</FormLabel>
                  <FormControl>
                    <Input type="number" min={1} step={1} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={mutation.isPending || zones.length === 0}>
                {mutation.isPending
                  ? isEdit
                    ? "Saving…"
                    : "Creating…"
                  : isEdit
                    ? "Save changes"
                    : "Create table"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function TableStatusSelect({
  branchId,
  table,
  disabled,
}: {
  branchId: string
  table: Table
  disabled: boolean
}) {
  const changeStatus = useChangeTableStatus(branchId, table.id)

  async function handleChange(next: string | null) {
    if (!next) return
    const status = next as TableStatus
    if (status === table.status) return
    try {
      await changeStatus.mutateAsync({ status, idempotencyKey: newIdempotencyKey() })
      toast.success(`Table ${table.tableNumber} marked ${status}.`)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to update table status.")
    }
  }

  return (
    <Select value={table.status} onValueChange={handleChange} disabled={disabled || changeStatus.isPending}>
      <SelectTrigger size="sm" aria-label={`Change status for table ${table.tableNumber}`}>
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
  )
}

export default function TablesPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId
  const [offset, setOffset] = React.useState(0)

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "table.read")
  const canManage = perms.hasAtBranch(branchId, "table.manage")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = useTables(
    branchId,
    { offset, limit: PAGE_SIZE },
    { enabled }
  )
  // Fetched once per page (not per row) and reused both for the "Dining
  // area" column below and the create/edit dialog's Select options --
  // the only alternative would be an N+1 lookup per table row.
  const zonesQuery = useTableZones(branchId, { offset: 0, limit: 100 }, { enabled })
  const zones = zonesQuery.data?.data ?? []
  const zoneNameById = new Map(zones.map((zone) => [zone.id, zone.name]))

  const tables = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Tables"
        description="Every table for this branch, its dining area, capacity, and current status."
        actions={
          canManage ? (
            <TableFormDialog
              branchId={branchId}
              zones={zones}
              trigger={
                <Button size="sm" disabled={zones.length === 0}>
                  <PlusIcon />
                  Add table
                </Button>
              }
            />
          ) : undefined
        }
      />

      <BranchSubNav branchId={branchId} />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="tables" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load tables."}
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
      ) : tables.length === 0 ? (
        <EmptyState
          icon={ArmchairIcon}
          title="No tables yet"
          description={
            zones.length === 0
              ? canManage
                ? "Add a dining area first, then add tables to it."
                : "No tables have been set up for this branch yet."
              : canManage
                ? "Add this branch's first table."
                : "No tables have been set up for this branch yet."
          }
          action={
            canManage && zones.length > 0 ? (
              <TableFormDialog
                branchId={branchId}
                zones={zones}
                trigger={
                  <Button size="sm">
                    <PlusIcon />
                    Add table
                  </Button>
                }
              />
            ) : canManage && zones.length === 0 ? (
              <Button size="sm" render={<Link href={`/branches/${branchId}/dining-areas`} />} nativeButton={false}>
                Go to dining areas
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <TableComponent>
            <TableHeader>
              <TableRow>
                <TableHead>Table</TableHead>
                <TableHead>Dining area</TableHead>
                <TableHead>Capacity</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {tables.map((table) => (
                <TableRow key={table.id}>
                  <TableCell className="font-medium">
                    <Link
                      href={`/branches/${branchId}/tables/${table.id}`}
                      className="hover:underline"
                    >
                      {table.tableNumber}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {zoneNameById.get(table.tableZoneId) ?? "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{table.capacity}</TableCell>
                  <TableCell>
                    {canManage ? (
                      <TableStatusSelect branchId={branchId} table={table} disabled={!canManage} />
                    ) : (
                      <TableStatusBadge status={table.status} />
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`QR codes for table ${table.tableNumber}`}
                        render={<Link href={`/branches/${branchId}/tables/${table.id}`} />}
                        nativeButton={false}
                      >
                        <QrCodeIcon />
                      </Button>
                      {canManage ? (
                        <TableFormDialog
                          branchId={branchId}
                          zones={zones}
                          table={table}
                          trigger={
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={`Edit table ${table.tableNumber}`}
                            >
                              <PencilIcon />
                            </Button>
                          }
                        />
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </TableComponent>
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
