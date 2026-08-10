import { Badge } from "@/components/ui/badge"
import type { TableStatus } from "@/types/table"

// The backend deliberately exposes these four statuses with no
// transition graph (Architecture SS7) -- this badge only labels the
// current value, it never implies or enforces an order between them.
const STATUS_VARIANT: Record<TableStatus, "default" | "secondary" | "destructive" | "outline"> = {
  available: "secondary",
  occupied: "default",
  reserved: "outline",
  cleaning: "destructive",
}

const STATUS_LABEL: Record<TableStatus, string> = {
  available: "Available",
  occupied: "Occupied",
  reserved: "Reserved",
  cleaning: "Cleaning",
}

export function TableStatusBadge({ status }: { status: TableStatus }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{STATUS_LABEL[status] ?? status}</Badge>
}
