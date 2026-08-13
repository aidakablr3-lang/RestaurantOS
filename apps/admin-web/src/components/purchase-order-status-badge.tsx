import { Badge } from "@/components/ui/badge"
import type { PurchaseOrderStatus } from "@/types/purchase-order"

const STATUS_VARIANT: Record<
  PurchaseOrderStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  draft: "outline",
  sent: "secondary",
  partially_received: "secondary",
  fully_received: "default",
  canceled: "destructive",
}

const STATUS_LABEL: Record<PurchaseOrderStatus, string> = {
  draft: "Draft",
  sent: "Sent",
  partially_received: "Partially received",
  fully_received: "Fully received",
  canceled: "Canceled",
}

export function PurchaseOrderStatusBadge({ status }: { status: PurchaseOrderStatus }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{STATUS_LABEL[status] ?? status}</Badge>
  )
}
