"use client"

import * as React from "react"
import { useParams } from "next/navigation"

import { BranchSubNav } from "@/components/branch-sub-nav"
import { PermissionRestricted } from "@/components/permission-restricted"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageHeader } from "@/components/ui/page-header"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useEndOfDayReport } from "@/hooks/use-reports"
import { usePermissionHelpers } from "@/hooks/use-permissions"

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10)
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold text-foreground">{value}</p>
      </CardContent>
    </Card>
  )
}

export default function EndOfDayReportPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId
  const [date, setDate] = React.useState(todayIsoDate)

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "reports.read")
  const enabled = !perms.isLoading && canRead

  const reportQuery = useEndOfDayReport(branchId, date, { enabled })
  const report = reportQuery.data?.data

  return (
    <div className="grid gap-6">
      <PageHeader
        title="End-of-day report"
        description="Sales, payments, and top items for a single day at this branch."
      />

      <BranchSubNav branchId={branchId} />

      {!canRead ? (
        <PermissionRestricted resource="reports" />
      ) : (
        <div className="grid gap-6">
          <div className="grid max-w-xs gap-1.5">
            <Label htmlFor="report-date">Date</Label>
            <Input
              id="report-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>

          {reportQuery.isLoading ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full rounded-xl" />
              ))}
            </div>
          ) : reportQuery.isError ? (
            <EmptyState
              title="Couldn't load this report"
              description="Please try a different date or try again."
            />
          ) : report ? (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatCard label="Orders" value={String(report.orderCount)} />
                <StatCard
                  label="Gross sales"
                  value={`${report.grossSalesAmount} ${report.currencyCode}`}
                />
                <StatCard
                  label="Net collected"
                  value={`${report.netCollectedAmount} ${report.currencyCode}`}
                />
                <StatCard
                  label="Outstanding"
                  value={`${report.outstandingAmount} ${report.currencyCode}`}
                />
                <StatCard label="Items sold" value={String(report.itemsSoldCount)} />
                <StatCard
                  label="Tips"
                  value={`${report.totalTipsAmount} ${report.currencyCode}`}
                />
                <StatCard
                  label="Refunded"
                  value={`${report.totalRefundedAmount} ${report.currencyCode}`}
                />
                <StatCard label="Voided orders" value={String(report.voidedOrderCount)} />
                <StatCard
                  label="Voided sales"
                  value={`${report.voidedSalesAmount} ${report.currencyCode}`}
                />
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Payments by tender type</CardTitle>
                </CardHeader>
                <CardContent>
                  {report.tenderBreakdown.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No settled payments this day.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Tender</TableHead>
                          <TableHead className="text-right">Payments</TableHead>
                          <TableHead className="text-right">Amount</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {report.tenderBreakdown.map((t) => (
                          <TableRow key={t.tenderType}>
                            <TableCell className="capitalize">{t.tenderType}</TableCell>
                            <TableCell className="text-right">{t.paymentCount}</TableCell>
                            <TableCell className="text-right">
                              {t.amount} {report.currencyCode}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Top items</CardTitle>
                </CardHeader>
                <CardContent>
                  {report.topItems.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No items sold this day.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Item</TableHead>
                          <TableHead className="text-right">Quantity sold</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {report.topItems.map((item) => (
                          <TableRow key={item.menuItemId}>
                            <TableCell>{item.name}</TableCell>
                            <TableCell className="text-right">{item.quantitySold}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </>
          ) : null}
        </div>
      )}
    </div>
  )
}
