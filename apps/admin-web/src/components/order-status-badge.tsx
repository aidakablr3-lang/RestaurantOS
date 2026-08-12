import { Badge } from "@/components/ui/badge"
import type { OrderItemLineStatus, OrderStatus } from "@/types/order"

const STATUS_VARIANT: Record<OrderStatus, "default" | "secondary" | "destructive" | "outline"> = {
  open: "outline",
  fired: "secondary",
  served: "secondary",
  billed: "default",
  closed: "default",
  voided: "destructive",
}

const STATUS_LABEL: Record<OrderStatus, string> = {
  open: "Open",
  fired: "Fired",
  served: "Served",
  billed: "Billed",
  closed: "Closed",
  voided: "Voided",
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{STATUS_LABEL[status] ?? status}</Badge>
}

const LINE_STATUS_VARIANT: Record<
  OrderItemLineStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  added: "outline",
  fired: "secondary",
  ready: "default",
  served: "secondary",
  voided: "destructive",
}

const LINE_STATUS_LABEL: Record<OrderItemLineStatus, string> = {
  added: "Added",
  fired: "Fired",
  ready: "Ready",
  served: "Served",
  voided: "Voided",
}

export function OrderItemLineStatusBadge({ status }: { status: OrderItemLineStatus }) {
  return (
    <Badge variant={LINE_STATUS_VARIANT[status] ?? "outline"}>
      {LINE_STATUS_LABEL[status] ?? status}
    </Badge>
  )
}
