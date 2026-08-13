import { Badge } from "@/components/ui/badge"
import type { BranchStatus } from "@/types/branch"

const STATUS_VARIANT: Record<
  BranchStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  opened: "secondary",
  active: "default",
  temporarily_closed: "destructive",
  permanently_closed: "outline",
}

const STATUS_LABEL: Record<BranchStatus, string> = {
  opened: "Opened",
  active: "Active",
  temporarily_closed: "Temporarily closed",
  permanently_closed: "Permanently closed",
}

export function BranchStatusBadge({ status }: { status: BranchStatus }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "outline"}>
      {STATUS_LABEL[status] ?? status}
    </Badge>
  )
}
