import { Badge } from "@/components/ui/badge"
import type { SupplierStatus } from "@/types/supplier"

const STATUS_VARIANT: Record<SupplierStatus, "default" | "secondary" | "destructive" | "outline"> = {
  active: "secondary",
  inactive: "outline",
}

const STATUS_LABEL: Record<SupplierStatus, string> = {
  active: "Active",
  inactive: "Inactive",
}

export function SupplierStatusBadge({ status }: { status: SupplierStatus }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{STATUS_LABEL[status] ?? status}</Badge>
}
