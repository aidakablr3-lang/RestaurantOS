"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { CalendarClockIcon, CheckIcon, PencilIcon, PlusIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import { BranchSubNav } from "@/components/branch-sub-nav"
import { PermissionRestricted } from "@/components/permission-restricted"
import { ReservationStatusBadge } from "@/components/reservation-status-badge"
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useCreateReservation, useReservations, useUpdateReservation } from "@/hooks/use-reservations"
import { useTables } from "@/hooks/use-tables"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { type ReservationFormValues, reservationSchema } from "@/lib/schemas/reservation"
import type { Reservation, ReservationStatus } from "@/types/reservation"
import type { Table as TableEntity } from "@/types/table"

const PAGE_SIZE = 20
const NO_TABLE = "none"

// Mirrors the domain entity's own transition graph exactly (Reservation.
// confirm/seat/complete/mark_no_show/cancel) -- this is a disclosed
// reflection of a real, backend-enforced graph, not an invented
// client-side rule the way a Table status graph would be (Table
// deliberately has none).
const NEXT_ACTIONS: Record<
  ReservationStatus,
  { label: string; target: ReservationStatus; icon: typeof CheckIcon; destructive?: boolean }[]
> = {
  requested: [
    { label: "Confirm", target: "confirmed", icon: CheckIcon },
    { label: "Cancel", target: "canceled", icon: XIcon, destructive: true },
  ],
  confirmed: [
    { label: "Seat", target: "seated", icon: CheckIcon },
    { label: "No-show", target: "no_show", icon: XIcon, destructive: true },
    { label: "Cancel", target: "canceled", icon: XIcon, destructive: true },
  ],
  seated: [{ label: "Complete", target: "completed", icon: CheckIcon }],
  completed: [],
  no_show: [],
  canceled: [],
}

function toDatetimeLocal(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function ReservationFormDialog({
  branchId,
  tables,
  reservation,
  trigger,
}: {
  branchId: string
  tables: TableEntity[]
  reservation?: Reservation
  trigger: React.ReactElement
}) {
  const [open, setOpen] = React.useState(false)
  const isEdit = Boolean(reservation)
  const createReservation = useCreateReservation(branchId)
  const updateReservation = useUpdateReservation(branchId, reservation?.id ?? "")
  const mutation = isEdit ? updateReservation : createReservation

  const defaults: ReservationFormValues = {
    partySize: reservation?.partySize ?? 2,
    requestedAt: reservation ? toDatetimeLocal(reservation.requestedAt) : "",
    tableId: reservation?.tableId ?? NO_TABLE,
  }

  const form = useForm<ReservationFormValues>({
    resolver: zodResolver(reservationSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: ReservationFormValues) {
    const tableId = !values.tableId || values.tableId === NO_TABLE ? null : values.tableId
    try {
      if (isEdit && reservation) {
        // Resubmitting the reservation's own current status keeps this a
        // plain field edit -- the backend treats target === current
        // status as "no transition requested."
        await updateReservation.mutateAsync({
          partySize: values.partySize,
          status: reservation.status,
          tableId,
        })
        toast.success("Reservation updated.")
      } else {
        await createReservation.mutateAsync({
          body: {
            partySize: values.partySize,
            requestedAt: new Date(values.requestedAt).toISOString(),
            tableId,
          },
          idempotencyKey: newIdempotencyKey(),
        })
        toast.success("Reservation created.")
      }
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to save this reservation.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit reservation" : "Add reservation"}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="partySize"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Party size</FormLabel>
                  <FormControl>
                    <Input type="number" min={1} step={1} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {!isEdit ? (
              <FormField
                control={form.control}
                name="requestedAt"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Requested for</FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}
            <FormField
              control={form.control}
              name="tableId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Table (optional)</FormLabel>
                  <Select value={field.value || NO_TABLE} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NO_TABLE}>No table assigned</SelectItem>
                      {tables.map((table) => (
                        <SelectItem key={table.id} value={table.id}>
                          Table {table.tableNumber}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
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
                    : "Create reservation"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function ReservationRowActions({
  branchId,
  reservation,
}: {
  branchId: string
  reservation: Reservation
}) {
  const updateReservation = useUpdateReservation(branchId, reservation.id)
  const actions = NEXT_ACTIONS[reservation.status]

  async function handleTransition(target: ReservationStatus) {
    try {
      await updateReservation.mutateAsync({
        partySize: reservation.partySize,
        status: target,
        tableId: reservation.tableId,
      })
      toast.success(`Reservation marked ${target.replace("_", "-")}.`)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to update this reservation."
      )
    }
  }

  if (actions.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-1">
      {actions.map((action) =>
        action.destructive ? (
          <AlertDialog key={action.target}>
            <AlertDialogTrigger
              render={
                <Button variant="outline" size="sm" disabled={updateReservation.isPending}>
                  <action.icon />
                  {action.label}
                </Button>
              }
            />
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Mark this reservation {action.label.toLowerCase()}?</AlertDialogTitle>
                <AlertDialogDescription>
                  This cannot be undone from here -- the reservation will move to a terminal
                  state.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={updateReservation.isPending}>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => handleTransition(action.target)}
                  disabled={updateReservation.isPending}
                >
                  {updateReservation.isPending ? "Saving…" : action.label}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        ) : (
          <Button
            key={action.target}
            variant="outline"
            size="sm"
            disabled={updateReservation.isPending}
            onClick={() => handleTransition(action.target)}
          >
            <action.icon />
            {action.label}
          </Button>
        )
      )}
    </div>
  )
}

export default function ReservationsPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId
  const [offset, setOffset] = React.useState(0)

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "reservation.read")
  const canManage = perms.hasAtBranch(branchId, "reservation.manage")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = useReservations(
    branchId,
    { offset, limit: PAGE_SIZE },
    { enabled }
  )

  // Fetched once and reused for both the "Table" column join and the
  // create/edit dialog's Select options -- avoids an N+1 fetch per row.
  const tablesQuery = useTables(branchId, { offset: 0, limit: 100 }, { enabled })
  const tables = tablesQuery.data?.data ?? []
  const tableNumberById = new Map(tables.map((table) => [table.id, table.tableNumber]))

  const reservations = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Reservations"
        description="Every reservation is a guest/walk-in row -- no customer profile is attached (no Customer entity exists yet)."
        actions={
          canManage ? (
            <ReservationFormDialog
              branchId={branchId}
              tables={tables}
              trigger={
                <Button size="sm">
                  <PlusIcon />
                  Add reservation
                </Button>
              }
            />
          ) : undefined
        }
      />

      <BranchSubNav branchId={branchId} />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="reservations" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load reservations."}
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
      ) : reservations.length === 0 ? (
        <EmptyState
          icon={CalendarClockIcon}
          title="No reservations yet"
          description={
            canManage
              ? "Add a reservation to start tracking this branch's bookings."
              : "No reservations have been made for this branch yet."
          }
          action={
            canManage ? (
              <ReservationFormDialog
                branchId={branchId}
                tables={tables}
                trigger={
                  <Button size="sm">
                    <PlusIcon />
                    Add reservation
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
                <TableHead>Requested for</TableHead>
                <TableHead>Party size</TableHead>
                <TableHead>Table</TableHead>
                <TableHead>Status</TableHead>
                {canManage ? <TableHead className="w-64">Actions</TableHead> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {reservations.map((reservation) => (
                <TableRow key={reservation.id}>
                  <TableCell className="font-medium">
                    {new Date(reservation.requestedAt).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{reservation.partySize}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {reservation.tableId
                      ? (tableNumberById.get(reservation.tableId) ?? reservation.tableId)
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <ReservationStatusBadge status={reservation.status} />
                  </TableCell>
                  {canManage ? (
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <ReservationRowActions branchId={branchId} reservation={reservation} />
                        <ReservationFormDialog
                          branchId={branchId}
                          tables={tables}
                          reservation={reservation}
                          trigger={
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={`Edit reservation for ${new Date(reservation.requestedAt).toLocaleString()}`}
                            >
                              <PencilIcon />
                            </Button>
                          }
                        />
                      </div>
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
