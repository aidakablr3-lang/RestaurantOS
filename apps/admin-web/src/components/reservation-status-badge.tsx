import { Badge } from "@/components/ui/badge"
import type { ReservationStatus } from "@/types/reservation"

const STATUS_VARIANT: Record<
  ReservationStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  requested: "outline",
  confirmed: "secondary",
  seated: "default",
  completed: "secondary",
  no_show: "destructive",
  canceled: "outline",
}

const STATUS_LABEL: Record<ReservationStatus, string> = {
  requested: "Requested",
  confirmed: "Confirmed",
  seated: "Seated",
  completed: "Completed",
  no_show: "No-show",
  canceled: "Canceled",
}

export function ReservationStatusBadge({ status }: { status: ReservationStatus }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{STATUS_LABEL[status] ?? status}</Badge>
  )
}
