"use client"

import * as React from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PercentIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

import { PermissionRestricted } from "@/components/permission-restricted"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Pagination } from "@/components/ui/pagination"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useCreateDiscount, useDiscounts } from "@/hooks/use-discounts"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { type CreateDiscountFormValues, createDiscountSchema } from "@/lib/schemas/discount"

const PAGE_SIZE = 20

const DISCOUNT_TYPE_LABEL: Record<string, string> = {
  percentage: "Percentage",
  fixed_amount: "Fixed amount",
}

function CreateDiscountDialog() {
  const [open, setOpen] = React.useState(false)
  const createDiscount = useCreateDiscount()

  const defaults: CreateDiscountFormValues = {
    name: "",
    discountType: "percentage",
    value: 10,
    requiresApproval: false,
  }

  const form = useForm<CreateDiscountFormValues>({
    resolver: zodResolver(createDiscountSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: CreateDiscountFormValues) {
    try {
      await createDiscount.mutateAsync({
        name: values.name,
        discountType: values.discountType,
        value: String(values.value),
        requiresApproval: values.requiresApproval,
      })
      toast.success("Discount created.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create this discount.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            Add discount
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a discount</DialogTitle>
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
                    <Input placeholder="Staff meal" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="discountType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} items={DISCOUNT_TYPE_LABEL}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="percentage">Percentage</SelectItem>
                      <SelectItem value="fixed_amount">Fixed amount</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {form.watch("discountType") === "percentage" ? "Percentage" : "Amount"}
                  </FormLabel>
                  <FormControl>
                    <Input type="number" min={0} step="0.01" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="requiresApproval"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center gap-2 space-y-0">
                  <FormControl>
                    <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                  <FormLabel className="font-normal">Requires manager approval to apply</FormLabel>
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={createDiscount.isPending}>
                {createDiscount.isPending ? "Creating…" : "Create discount"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function DiscountsPage() {
  const [offset, setOffset] = React.useState(0)
  const perms = usePermissionHelpers()
  // ListDiscountsUseCase and CreateDiscountUseCase are both gated on the
  // same tenant-wide billing.manage permission -- there is no separate
  // read-only grant for discounts on the backend.
  const canAccess = perms.hasTenantWide("billing.manage")

  const { data, isLoading, isError, error, refetch } = useDiscounts(
    { offset, limit: PAGE_SIZE },
    { enabled: !perms.isLoading && canAccess }
  )

  const discounts = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Discounts"
        description="Manual discounts, comps, and write-offs applied to bills across every branch in this tenant."
        actions={canAccess ? <CreateDiscountDialog /> : undefined}
      />

      {!perms.isLoading && !canAccess ? (
        <PermissionRestricted resource="discounts" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load discounts."}
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
      ) : discounts.length === 0 ? (
        <EmptyState
          icon={PercentIcon}
          title="No discounts yet"
          description="Add a discount like Staff Meal or Happy Hour, then apply it to a bill."
          action={<CreateDiscountDialog />}
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Approval</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {discounts.map((discount) => (
                <TableRow key={discount.id}>
                  <TableCell className="font-medium">{discount.name}</TableCell>
                  <TableCell className="text-muted-foreground capitalize">
                    {discount.discountType.replace("_", " ")}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {discount.discountType === "percentage" ? `${discount.value}%` : discount.value}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {discount.requiresApproval ? "Required" : "Not required"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {meta && meta.total > 0 ? (
        <Pagination offset={meta.offset} limit={meta.limit} total={meta.total} onOffsetChange={setOffset} />
      ) : null}
    </div>
  )
}
