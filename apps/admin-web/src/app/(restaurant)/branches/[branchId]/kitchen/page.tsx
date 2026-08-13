"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { ChefHatIcon } from "lucide-react"
import { toast } from "sonner"

import { BranchSubNav } from "@/components/branch-sub-nav"
import { KitchenItemStatusBadge, KitchenTicketStatusBadge } from "@/components/kitchen-ticket-status-badge"
import { PermissionRestricted } from "@/components/permission-restricted"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { Skeleton } from "@/components/ui/skeleton"
import { useChangeKitchenItemStatus, useChangeKitchenTicketStatus, useKitchenTickets } from "@/hooks/use-kitchen"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import type { KitchenItemStatus, KitchenTicket, KitchenTicketStatus } from "@/types/kitchen"

const REFETCH_INTERVAL_MS = 8_000

const NEXT_TICKET_STATUS: Partial<Record<KitchenTicketStatus, KitchenTicketStatus>> = {
  fired: "in_progress",
  in_progress: "ready",
  ready: "served",
}

const NEXT_ITEM_STATUS: Partial<Record<KitchenItemStatus, KitchenItemStatus>> = {
  queued: "in_progress",
  in_progress: "ready",
  ready: "served",
}

function TicketCard({ ticket, branchId, canManage }: { ticket: KitchenTicket; branchId: string; canManage: boolean }) {
  const changeTicketStatus = useChangeKitchenTicketStatus(branchId)
  const changeItemStatus = useChangeKitchenItemStatus(branchId)

  async function advanceTicket() {
    const target = NEXT_TICKET_STATUS[ticket.status]
    if (!target) return
    try {
      await changeTicketStatus.mutateAsync({
        kitchenTicketId: ticket.id,
        body: { status: target },
        idempotencyKey: newIdempotencyKey(),
      })
      toast.success(`Ticket marked ${target.replace("_", " ")}.`)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to update this ticket.")
    }
  }

  async function advanceItem(itemId: string, current: KitchenItemStatus) {
    const target = NEXT_ITEM_STATUS[current]
    if (!target) return
    try {
      await changeItemStatus.mutateAsync({
        kitchenItemId: itemId,
        body: { status: target },
        idempotencyKey: newIdempotencyKey(),
      })
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to update this item.")
    }
  }

  const ticketNextLabel = NEXT_TICKET_STATUS[ticket.status]

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>{ticket.station}</CardTitle>
        <KitchenTicketStatusBadge status={ticket.status} />
      </CardHeader>
      <CardContent className="grid gap-3">
        <ul className="grid gap-2">
          {ticket.items.map((item) => {
            const nextItemLabel = NEXT_ITEM_STATUS[item.status]
            return (
              <li key={item.id} className="flex items-center justify-between gap-2 rounded-md border px-2.5 py-1.5">
                <KitchenItemStatusBadge status={item.status} />
                {canManage && nextItemLabel ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={changeItemStatus.isPending}
                    onClick={() => advanceItem(item.id, item.status)}
                  >
                    Mark {nextItemLabel.replace("_", " ")}
                  </Button>
                ) : null}
              </li>
            )
          })}
        </ul>
        {canManage && ticketNextLabel ? (
          <Button size="sm" disabled={changeTicketStatus.isPending} onClick={advanceTicket}>
            {changeTicketStatus.isPending ? "Saving…" : `Mark ticket ${ticketNextLabel.replace("_", " ")}`}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}

export default function KitchenPage() {
  const params = useParams<{ branchId: string }>()
  const branchId = params.branchId

  const perms = usePermissionHelpers()
  const canRead = perms.hasAtBranch(branchId, "kitchen.read")
  const canManage = perms.hasAtBranch(branchId, "kitchen.manage")
  const enabled = !perms.isLoading && canRead

  const { data, isLoading, isError, error, refetch } = useKitchenTickets(
    branchId,
    { offset: 0, limit: 50 },
    { enabled, refetchInterval: enabled ? REFETCH_INTERVAL_MS : undefined }
  )

  const tickets = (data?.data ?? []).filter((ticket) => ticket.status !== "served")
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Kitchen display"
        description="Auto-refreshes every few seconds. Served tickets drop off the board."
      />

      <BranchSubNav branchId={branchId} />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="the kitchen display" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load kitchen tickets."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : loading ? (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-40 w-full" />
          ))}
        </div>
      ) : tickets.length === 0 ? (
        <EmptyState icon={ChefHatIcon} title="No active tickets" description="Fired orders will appear here." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tickets.map((ticket) => (
            <TicketCard key={ticket.id} ticket={ticket} branchId={branchId} canManage={canManage} />
          ))}
        </div>
      )}
    </div>
  )
}
