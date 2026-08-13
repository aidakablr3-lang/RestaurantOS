"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PlusIcon, TagIcon } from "lucide-react"
import { toast } from "sonner"

import { BillStatusBadge } from "@/components/bill-status-badge"
import { PaymentStatusBadge } from "@/components/payment-status-badge"
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
import { useApplyBillAdjustment, useBill } from "@/hooks/use-bills"
import { usePayments, useRecordPayment } from "@/hooks/use-payments"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import {
  type ApplyBillAdjustmentFormValues,
  applyBillAdjustmentSchema,
  type RecordPaymentFormValues,
  recordPaymentSchema,
} from "@/lib/schemas/bill"
import { useCurrentUserId } from "@/lib/current-user"

// "tip" is deliberately excluded -- a tip is not part of the
// restaurant bill (P0 correction, 2026-08-12); the backend rejects any
// attempt to apply one as a bill adjustment.
const ADJUSTMENT_TYPE_LABEL: Record<string, string> = {
  discount: "Discount",
  service_charge: "Service charge",
  comp: "Comp",
  write_off: "Write-off",
}

const TENDER_TYPE_LABEL: Record<string, string> = {
  cash: "Cash",
  card: "Card",
  wallet: "Wallet",
}

function ApplyAdjustmentDialog({ billId }: { billId: string }) {
  const [open, setOpen] = React.useState(false)
  const applyAdjustment = useApplyBillAdjustment(billId)
  const currentUserId = useCurrentUserId()

  const defaults: ApplyBillAdjustmentFormValues = { adjustmentType: "discount", amount: 0, reason: "" }
  const form = useForm<ApplyBillAdjustmentFormValues>({
    resolver: zodResolver(applyBillAdjustmentSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: ApplyBillAdjustmentFormValues) {
    try {
      await applyAdjustment.mutateAsync({
        adjustmentType: values.adjustmentType,
        amount: String(values.amount),
        reason: values.reason || null,
        approvedByUserId: currentUserId,
      })
      toast.success("Adjustment applied.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to apply this adjustment.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm" variant="secondary">
            <TagIcon />
            Apply adjustment
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Apply an adjustment</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="adjustmentType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={ADJUSTMENT_TYPE_LABEL}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {Object.entries(ADJUSTMENT_TYPE_LABEL).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
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
              name="amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Amount</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} step="0.01" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={applyAdjustment.isPending}>
                {applyAdjustment.isPending ? "Applying…" : "Apply adjustment"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function RecordPaymentDialog({ billId }: { billId: string }) {
  const [open, setOpen] = React.useState(false)
  const recordPayment = useRecordPayment(billId)

  const defaults: RecordPaymentFormValues = { tenderType: "cash", amount: 0 }
  const form = useForm<RecordPaymentFormValues>({
    resolver: zodResolver(recordPaymentSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: RecordPaymentFormValues) {
    try {
      await recordPayment.mutateAsync({
        tenderType: values.tenderType,
        amount: String(values.amount),
      })
      toast.success("Payment recorded.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to record this payment.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            Record payment
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Record a payment</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="tenderType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Tender</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={TENDER_TYPE_LABEL}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="cash">Cash</SelectItem>
                      <SelectItem value="card">Card</SelectItem>
                      <SelectItem value="wallet">Wallet</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Amount to pay</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} step="0.01" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={recordPayment.isPending}>
                {recordPayment.isPending ? "Recording…" : "Record payment"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function BillDetailPage() {
  const params = useParams<{ billId: string }>()
  const billId = params.billId

  const perms = usePermissionHelpers()
  const canRead = perms.hasAnywhere("billing.read")
  const canManage = perms.hasAnywhere("billing.manage")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = useBill(billId, { enabled })
  const bill = data?.data
  const paymentsQuery = usePayments(billId, { enabled })
  const payments = paymentsQuery.data?.data ?? []

  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader title="Bill" description="Tax lines, adjustments, and payments for a single order's bill." />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="this bill" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load this bill."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : loading || !bill ? (
        <div className="grid gap-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : (
        <>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Summary</CardTitle>
              <BillStatusBadge status={bill.status} />
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
              <div>
                <p className="text-xs text-muted-foreground">Subtotal</p>
                <p className="font-medium">{bill.subtotalAmount}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Tax</p>
                <p className="font-medium">{bill.taxAmount}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Adjustments</p>
                <p className="font-medium">{bill.adjustmentsTotal}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Amount due</p>
                <p className="font-medium">{bill.amountDue}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Amount paid</p>
                <p className="font-medium">{bill.amountPaid}</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Adjustments</CardTitle>
              {canManage && bill.status !== "closed" ? <ApplyAdjustmentDialog billId={billId} /> : null}
            </CardHeader>
            <CardContent>
              {bill.adjustments.length === 0 ? (
                <p className="text-sm text-muted-foreground">No adjustments applied.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Reason</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {bill.adjustments.map((adjustment) => (
                      <TableRow key={adjustment.id}>
                        <TableCell>{ADJUSTMENT_TYPE_LABEL[adjustment.adjustmentType] ?? adjustment.adjustmentType}</TableCell>
                        <TableCell className="text-muted-foreground">{adjustment.amount}</TableCell>
                        <TableCell className="text-muted-foreground">{adjustment.reason ?? "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Payments</CardTitle>
              {canManage && bill.status !== "closed" ? <RecordPaymentDialog billId={billId} /> : null}
            </CardHeader>
            <CardContent>
              {payments.length === 0 ? (
                <p className="text-sm text-muted-foreground">No payments recorded yet.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tender</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {payments.map((payment) => (
                      <TableRow key={payment.id}>
                        <TableCell className="capitalize">{payment.tenderType}</TableCell>
                        <TableCell className="text-muted-foreground">{payment.amount}</TableCell>
                        <TableCell>
                          <PaymentStatusBadge status={payment.status} />
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
