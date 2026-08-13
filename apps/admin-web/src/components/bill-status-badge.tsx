import { Badge } from "@/components/ui/badge"
import type { BillStatus } from "@/types/bill"

const STATUS_VARIANT: Record<BillStatus, "default" | "secondary" | "destructive" | "outline"> = {
  open: "outline",
  partially_paid: "secondary",
  closed: "default",
}

const STATUS_LABEL: Record<BillStatus, string> = {
  open: "Open",
  partially_paid: "Partially paid",
  closed: "Closed",
}

export function BillStatusBadge({ status }: { status: BillStatus }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{STATUS_LABEL[status] ?? status}</Badge>
}
