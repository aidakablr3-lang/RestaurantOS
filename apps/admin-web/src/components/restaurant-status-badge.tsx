import { Badge } from "@/components/ui/badge"
import type { RestaurantStatus } from "@/types/restaurant"

const STATUS_VARIANT: Record<
  RestaurantStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  active: "default",
  discontinued: "outline",
}

export function RestaurantStatusBadge({ status }: { status: RestaurantStatus }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "outline"} className="capitalize">
      {status}
    </Badge>
  )
}
