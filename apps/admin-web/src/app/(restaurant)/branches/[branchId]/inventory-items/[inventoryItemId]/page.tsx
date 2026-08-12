"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PlusIcon } from "lucide-react"
import { toast } from "sonner"

import { PermissionRestricted } from "@/components/permission-restricted"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useInventoryItem, useRecordStockMovement, useStockMovements } from "@/hooks/use-inventory"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useCurrentUserId } from "@/lib/current-user"
import { ApiError } from "@/lib/api-client"
import {
  type RecordStockMovementFormValues,
  recordStockMovementSchema,
} from "@/lib/schemas/inventory-item"

const MOVEMENT_TYPE_LABEL: Record<string, string> = {
  adjustment: "Adjustment",
  waste: "Waste",
  transfer: "Transfer",
  sale_deduction: "Sale deduction",
  receipt: "Receipt",
}

function RecordMovementDialog({ branchId, inventoryItemId }: { branchId: string; inventoryItemId: string }) {
  const [open, setOpen] = React.useState(false)
  const recordMovement = useRecordStockMovement(branchId, inventoryItemId)
  const currentUserId = useCurrentUserId()

  const defaults: RecordStockMovementFormValues = { movementType: "adjustment", quantityDelta: 0, reason: "" }
  const form = useForm<RecordStockMovementFormValues>({
    resolver: zodResolver(recordStockMovementSchema),
    defaultValues: defaults,
  })
  const movementType = form.watch("movementType")

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: RecordStockMovementFormValues) {
    try {
      await recordMovement.mutateAsync({
        movementType: values.movementType,
        quantityDelta: String(values.quantityDelta),
        reason: values.movementType === "adjustment" ? values.reason || null : null,
        approvedByUserId: values.movementType === "adjustment" ? currentUserId : null,
      })
      toast.success("Stock movement recorded.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to record this movement.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            Record movement
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Record a stock movement</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="movementType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={MOVEMENT_TYPE_LABEL}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="adjustment">Adjustment (recount)</SelectItem>
                      <SelectItem value="waste">Waste</SelectItem>
                      <SelectItem value="transfer">Transfer</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="quantityDelta"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {movementType === "waste"
                      ? "Quantity wasted (always removes stock)"
                      : "Quantity delta (negative removes stock)"}
                  </FormLabel>
                  <FormControl>
                    <Input type="number" step="0.01" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {movementType === "adjustment" ? (
              <FormField
                control={form.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reason</FormLabel>
                    <FormControl>
                      <Input placeholder="Recount after stock take" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}
            <DialogFooter>
              <Button type="submit" disabled={recordMovement.isPending}>
                {recordMovement.isPending ? "Recording…" : "Record movement"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function InventoryItemDetailPage() {
  const params = useParams<{ branchId: string; inventoryItemId: string }>()
  const branchId = params.branchId
  const inventoryItemId = params.inventoryItemId

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "inventory.read")
  const canManage = perms.hasAtBranch(branchId, "inventory.manage")
  const enabled = !perms.isLoading && canRead

  const itemQuery = useInventoryItem(branchId, inventoryItemId, { enabled })
  const item = itemQuery.data?.data
  const movementsQuery = useStockMovements(inventoryItemId, { offset: 0, limit: 50 }, { enabled })
  const movements = movementsQuery.data?.data ?? []

  const loading = perms.isLoading || itemQuery.isLoading

  return (
    <div className="grid gap-6">
      <PageHeader title={item ? item.name : "Inventory item"} description="Stock movement history for this item." />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="this inventory item" />
      ) : itemQuery.isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {itemQuery.error instanceof ApiError ? itemQuery.error.message : "Failed to load this item."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => itemQuery.refetch()}>
            Retry
          </Button>
        </div>
      ) : loading || !item ? (
        <div className="grid gap-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground">On hand</p>
                <p className="font-medium">
                  {item.quantityOnHand} {item.unit}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Reorder point</p>
                <p className="font-medium">{item.reorderPoint ?? "—"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Negative stock override</p>
                <p className="font-medium">
                  {item.allowNegativeStockOverride === null
                    ? "Branch default"
                    : item.allowNegativeStockOverride
                      ? "Allowed"
                      : "Blocked"}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Stock movements</CardTitle>
              {canManage ? <RecordMovementDialog branchId={branchId} inventoryItemId={inventoryItemId} /> : null}
            </CardHeader>
            <CardContent>
              {movements.length === 0 ? (
                <p className="text-sm text-muted-foreground">No stock movements recorded yet.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Delta</TableHead>
                      <TableHead>Occurred</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {movements.map((movement) => (
                      <TableRow key={movement.id}>
                        <TableCell>{MOVEMENT_TYPE_LABEL[movement.movementType] ?? movement.movementType}</TableCell>
                        <TableCell className="text-muted-foreground">{movement.quantityDelta}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(movement.occurredAt).toLocaleString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
