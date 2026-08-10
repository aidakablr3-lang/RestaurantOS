"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { LayoutGridIcon, PencilIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

import { BranchSubNav } from "@/components/branch-sub-nav"
import { PermissionRestricted } from "@/components/permission-restricted"
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
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCreateTableZone, useTableZones, useUpdateTableZone } from "@/hooks/use-table-zones"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { type TableZoneFormValues, tableZoneSchema } from "@/lib/schemas/table-zone"
import type { TableZone } from "@/types/table-zone"

const PAGE_SIZE = 20

function TableZoneFormDialog({
  branchId,
  tableZone,
  trigger,
}: {
  branchId: string
  tableZone?: TableZone
  trigger: React.ReactElement
}) {
  const [open, setOpen] = React.useState(false)
  const isEdit = Boolean(tableZone)
  const createTableZone = useCreateTableZone(branchId)
  const updateTableZone = useUpdateTableZone(branchId, tableZone?.id ?? "")
  const mutation = isEdit ? updateTableZone : createTableZone

  const form = useForm<TableZoneFormValues>({
    resolver: zodResolver(tableZoneSchema),
    defaultValues: {
      name: tableZone?.name ?? "",
      displayOrder: tableZone?.displayOrder ?? 0,
    },
  })

  function handleOpenChange(next: boolean) {
    if (next) {
      form.reset({ name: tableZone?.name ?? "", displayOrder: tableZone?.displayOrder ?? 0 })
    }
    setOpen(next)
  }

  async function onSubmit(values: TableZoneFormValues) {
    try {
      if (isEdit) {
        await updateTableZone.mutateAsync(values)
        toast.success("Dining area updated.")
      } else {
        await createTableZone.mutateAsync({ body: values, idempotencyKey: newIdempotencyKey() })
        toast.success("Dining area created.")
      }
      setOpen(false)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to save this dining area."
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit dining area" : "Add dining area"}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Patio" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="displayOrder"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Display order</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} step={1} {...field} />
                  </FormControl>
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
                    : "Create dining area"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function DiningAreasPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId
  const [offset, setOffset] = React.useState(0)

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "table.read")
  const canManage = perms.hasAtBranch(branchId, "table.manage")

  const { data, isLoading, isError, error, refetch } = useTableZones(
    branchId,
    { offset, limit: PAGE_SIZE },
    { enabled: !perms.isLoading && canRead }
  )

  const tableZones = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Dining areas"
        description="Group this branch's tables into zones like Patio, Bar, or Main Floor."
        actions={
          canManage ? (
            <TableZoneFormDialog
              branchId={branchId}
              trigger={
                <Button size="sm">
                  <PlusIcon />
                  Add dining area
                </Button>
              }
            />
          ) : undefined
        }
      />

      <BranchSubNav branchId={branchId} />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="dining areas" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load dining areas."}
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
      ) : tableZones.length === 0 ? (
        <EmptyState
          icon={LayoutGridIcon}
          title="No dining areas yet"
          description={
            canManage
              ? "Add a dining area before creating tables -- every table belongs to one."
              : "No dining areas have been set up for this branch yet."
          }
          action={
            canManage ? (
              <TableZoneFormDialog
                branchId={branchId}
                trigger={
                  <Button size="sm">
                    <PlusIcon />
                    Add dining area
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
                <TableHead>Display order</TableHead>
                {canManage ? <TableHead className="w-20" /> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {tableZones.map((zone) => (
                <TableRow key={zone.id}>
                  <TableCell className="font-medium">{zone.name}</TableCell>
                  <TableCell className="text-muted-foreground">{zone.displayOrder}</TableCell>
                  {canManage ? (
                    <TableCell>
                      <TableZoneFormDialog
                        branchId={branchId}
                        tableZone={zone}
                        trigger={
                          <Button variant="ghost" size="icon" aria-label={`Edit ${zone.name}`}>
                            <PencilIcon />
                          </Button>
                        }
                      />
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
