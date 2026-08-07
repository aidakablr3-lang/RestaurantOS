import { Badge } from "@/components/ui/badge"
import type { TenantStatus } from "@/lib/api-types"

const STATUS_VARIANT: Record<
  TenantStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  ACTIVE: "default",
  PENDING: "secondary",
  SUSPENDED: "destructive",
  OFFBOARDED: "outline",
}

export function TenantStatusBadge({ status }: { status: TenantStatus }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{status}</Badge>
}
