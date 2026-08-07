import { Badge } from "@/components/ui/badge"
import type { TenantStatus } from "@/lib/api-types"

const STATUS_VARIANT: Record<
  TenantStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  provisioning: "secondary",
  active: "default",
  suspended: "destructive",
  migrating: "secondary",
  offboarded: "outline",
}

export function TenantStatusBadge({ status }: { status: TenantStatus }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "outline"} className="capitalize">
      {status}
    </Badge>
  )
}
