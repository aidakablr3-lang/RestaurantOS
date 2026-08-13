import { Badge } from "@/components/ui/badge"
import type { KitchenItemStatus, KitchenTicketStatus } from "@/types/kitchen"

const TICKET_STATUS_VARIANT: Record<
  KitchenTicketStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  fired: "outline",
  in_progress: "secondary",
  ready: "default",
  served: "secondary",
}

const TICKET_STATUS_LABEL: Record<KitchenTicketStatus, string> = {
  fired: "Fired",
  in_progress: "In progress",
  ready: "Ready",
  served: "Served",
}

export function KitchenTicketStatusBadge({ status }: { status: KitchenTicketStatus }) {
  return (
    <Badge variant={TICKET_STATUS_VARIANT[status] ?? "outline"}>
      {TICKET_STATUS_LABEL[status] ?? status}
    </Badge>
  )
}

const ITEM_STATUS_VARIANT: Record<
  KitchenItemStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  queued: "outline",
  in_progress: "secondary",
  ready: "default",
  served: "secondary",
}

const ITEM_STATUS_LABEL: Record<KitchenItemStatus, string> = {
  queued: "Queued",
  in_progress: "In progress",
  ready: "Ready",
  served: "Served",
}

export function KitchenItemStatusBadge({ status }: { status: KitchenItemStatus }) {
  return (
    <Badge variant={ITEM_STATUS_VARIANT[status] ?? "outline"}>
      {ITEM_STATUS_LABEL[status] ?? status}
    </Badge>
  )
}
