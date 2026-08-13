import { Badge } from "@/components/ui/badge"
import type { QRCodeStatus } from "@/types/qr-code"

const STATUS_VARIANT: Record<QRCodeStatus, "default" | "outline"> = {
  active: "default",
  revoked: "outline",
}

const STATUS_LABEL: Record<QRCodeStatus, string> = {
  active: "Active",
  revoked: "Revoked",
}

export function QRCodeStatusBadge({ status }: { status: QRCodeStatus }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{STATUS_LABEL[status] ?? status}</Badge>
}
