"use client"

import * as React from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PercentIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

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
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { useCreateTax, useTaxes } from "@/hooks/use-bills"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { type CreateTaxFormValues, createTaxSchema } from "@/lib/schemas/tax"
import type { Tax } from "@/types/bill"

function CreateTaxDialog() {
  const [open, setOpen] = React.useState(false)
  const createTax = useCreateTax()

  const defaults: CreateTaxFormValues = { name: "", rate: 0.1 }
  const form = useForm<CreateTaxFormValues>({
    resolver: zodResolver(createTaxSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: CreateTaxFormValues) {
    try {
      await createTax.mutateAsync({ name: values.name, rate: String(values.rate) })
      toast.success("Tax created.")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create this tax.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            Add tax
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a tax</DialogTitle>
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
                    <Input placeholder="VAT" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="rate"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Rate (0–1, e.g. 0.10 for 10%)</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} max={1} step="0.0001" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={createTax.isPending}>
                {createTax.isPending ? "Creating…" : "Create tax"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function TaxesPage() {
  const perms = usePermissionHelpers()
  const canAccess = perms.hasTenantWide("billing.manage")
  const canRead = canAccess || perms.hasTenantWide("billing.read")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = useTaxes({ enabled })
  const taxes: Tax[] = data?.data ?? []
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Taxes"
        description="Every active tax is applied automatically when a bill is generated from an order."
        actions={canAccess ? <CreateTaxDialog /> : undefined}
      />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="taxes" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load taxes."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : loading ? (
        <div className="grid gap-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : taxes.length === 0 ? (
        <EmptyState
          icon={PercentIcon}
          title="No taxes yet"
          description={canAccess ? "Add a tax to apply it automatically to every new bill." : "No taxes have been created for this tenant yet."}
          action={canAccess ? <CreateTaxDialog /> : undefined}
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Rate</TableHead>
                <TableHead>Active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {taxes.map((tax) => (
                <TableRow key={tax.id}>
                  <TableCell className="font-medium">{tax.name}</TableCell>
                  <TableCell className="text-muted-foreground">{tax.rate}</TableCell>
                  <TableCell className="text-muted-foreground">{tax.isActive ? "Yes" : "No"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
