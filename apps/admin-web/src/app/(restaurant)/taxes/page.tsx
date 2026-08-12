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
import { useCreateTax } from "@/hooks/use-bills"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { type CreateTaxFormValues, createTaxSchema } from "@/lib/schemas/tax"
import type { Tax } from "@/types/bill"

function CreateTaxDialog({ onCreated }: { onCreated: (tax: Tax) => void }) {
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
      const result = await createTax.mutateAsync({ name: values.name, rate: String(values.rate) })
      toast.success("Tax created.")
      onCreated(result.data)
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
  // The backend has no GET /api/v1/taxes list endpoint (disclosed in its
  // own router docstring) -- every active Tax is applied automatically
  // when a bill is generated, so nothing in this step's own scope reads
  // the full catalog back. This page can only show what was created in
  // the current browser session, not the tenant's full tax history.
  const [createdThisSession, setCreatedThisSession] = React.useState<Tax[]>([])

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Taxes"
        description="Every active tax is applied automatically when a bill is generated from an order."
        actions={canAccess ? <CreateTaxDialog onCreated={(tax) => setCreatedThisSession((prev) => [tax, ...prev])} /> : undefined}
      />

      {!perms.isLoading && !canAccess ? (
        <PermissionRestricted resource="taxes" />
      ) : createdThisSession.length === 0 ? (
        <EmptyState
          icon={PercentIcon}
          title="No taxes created this session"
          description="There is no listing endpoint for existing taxes -- taxes you create here appear below until you leave this page."
          action={<CreateTaxDialog onCreated={(tax) => setCreatedThisSession((prev) => [tax, ...prev])} />}
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
              {createdThisSession.map((tax) => (
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
