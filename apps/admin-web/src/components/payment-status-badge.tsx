import { Badge } from "@/components/ui/badge"
import type { PaymentStatus } from "@/types/payment"

const PAYMENT_STATUS_VARIANT: Record<
  PaymentStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  authorized: "outline",
  captured: "secondary",
  settled: "default",
  declined: "destructive",
}

const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
  authorized: "Authorized",
  captured: "Captured",
  settled: "Settled",
  declined: "Declined",
}

export function PaymentStatusBadge({ status }: { status: PaymentStatus }) {
  return (
    <Badge variant={PAYMENT_STATUS_VARIANT[status] ?? "outline"}>
      {PAYMENT_STATUS_LABEL[status] ?? status}
    </Badge>
  )
}
