import { Badge } from "@/components/ui/badge"
import type { PaymentStatus, RefundStatus } from "@/types/payment"

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

const REFUND_STATUS_VARIANT: Record<
  RefundStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  requested: "outline",
  approved: "secondary",
  processed: "default",
}

const REFUND_STATUS_LABEL: Record<RefundStatus, string> = {
  requested: "Requested",
  approved: "Approved",
  processed: "Processed",
}

export function RefundStatusBadge({ status }: { status: RefundStatus }) {
  return (
    <Badge variant={REFUND_STATUS_VARIANT[status] ?? "outline"}>
      {REFUND_STATUS_LABEL[status] ?? status}
    </Badge>
  )
}
