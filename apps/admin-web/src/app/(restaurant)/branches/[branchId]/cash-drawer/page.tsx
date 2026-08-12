"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { BranchSubNav } from "@/components/branch-sub-nav"
import { PermissionRestricted } from "@/components/permission-restricted"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { useCloseCashDrawer, useOpenCashDrawer } from "@/hooks/use-cash-drawers"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import {
  type CloseCashDrawerFormValues,
  closeCashDrawerSchema,
  type OpenCashDrawerFormValues,
  openCashDrawerSchema,
} from "@/lib/schemas/cash-drawer"
import type { CashDrawer } from "@/types/cash-drawer"

export default function CashDrawerPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId

  const perms = usePermissionHelpers()
  const canManage = perms.hasAtBranch(branchId, "billing.manage")

  // The backend has no GET endpoint for "the currently open drawer at
  // this branch" (only POST to open and POST .../close, both disclosed
  // in cash_drawer_router.py's own docstring) -- this page can only
  // track the drawer it itself opened, for as long as this tab stays
  // open. Reloading the page loses track of an already-open drawer.
  const [drawer, setDrawer] = React.useState<CashDrawer | null>(null)
  const [closed, setClosed] = React.useState<CashDrawer | null>(null)

  const openDrawer = useOpenCashDrawer(branchId)
  const closeDrawer = useCloseCashDrawer()

  const openForm = useForm<OpenCashDrawerFormValues>({
    resolver: zodResolver(openCashDrawerSchema),
    defaultValues: { openingFloatAmount: 0, terminalId: "" },
  })

  const closeForm = useForm<CloseCashDrawerFormValues>({
    resolver: zodResolver(closeCashDrawerSchema),
    defaultValues: { closingCountedAmount: 0 },
  })

  async function onOpen(values: OpenCashDrawerFormValues) {
    try {
      const result = await openDrawer.mutateAsync({
        openingFloatAmount: String(values.openingFloatAmount),
        terminalId: values.terminalId || null,
      })
      setDrawer(result.data)
      setClosed(null)
      toast.success("Cash drawer opened.")
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to open a cash drawer.")
    }
  }

  async function onClose(values: CloseCashDrawerFormValues) {
    if (!drawer) return
    try {
      const result = await closeDrawer.mutateAsync({
        cashDrawerId: drawer.id,
        body: { closingCountedAmount: String(values.closingCountedAmount) },
      })
      setClosed(result.data)
      setDrawer(null)
      toast.success("Cash drawer closed.")
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to close this cash drawer.")
    }
  }

  return (
    <div className="grid gap-6">
      <PageHeader title="Cash drawer" description="Open a drawer at the start of a shift, close it to reconcile." />

      <BranchSubNav branchId={branchId} />

      {!canManage ? (
        <PermissionRestricted resource="the cash drawer" />
      ) : drawer ? (
        <Card>
          <CardHeader>
            <CardTitle>Drawer open</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <p className="text-sm text-muted-foreground">
              Opened with a float of {drawer.openingFloatAmount} at{" "}
              {new Date(drawer.openedAt).toLocaleString()}.
            </p>
            <Form {...closeForm}>
              <form onSubmit={closeForm.handleSubmit(onClose)} className="grid max-w-sm gap-4" noValidate>
                <FormField
                  control={closeForm.control}
                  name="closingCountedAmount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Counted cash</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step="0.01" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" disabled={closeDrawer.isPending} className="w-fit">
                  {closeDrawer.isPending ? "Closing…" : "Close drawer"}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Open a drawer</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            {closed ? (
              <div className="grid gap-1 rounded-lg border bg-muted/40 p-4 text-sm">
                <p className="font-medium">Last drawer closed</p>
                <p className="text-muted-foreground">
                  Expected {closed.expectedCashAmount ?? "—"}, counted {closed.closingCountedAmount}, variance{" "}
                  {closed.varianceAmount ?? "—"}.
                </p>
              </div>
            ) : null}
            <Form {...openForm}>
              <form onSubmit={openForm.handleSubmit(onOpen)} className="grid max-w-sm gap-4" noValidate>
                <FormField
                  control={openForm.control}
                  name="openingFloatAmount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Opening float</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step="0.01" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={openForm.control}
                  name="terminalId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Terminal (optional)</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" disabled={openDrawer.isPending} className="w-fit">
                  {openDrawer.isPending ? "Opening…" : "Open drawer"}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
