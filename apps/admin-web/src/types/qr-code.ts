/**
 * Mirrors modules/restaurant/presentation/api/v1/qr_code_router.py's
 * QRCodeResponseSchema and the domain's QRCodeStatus StrEnum. Field
 * names are camelCase on the wire.
 *
 * No request type exists -- POST /api/v1/tables/{id}/qr-codes takes no
 * body; the table comes from the path and everything else is
 * generated server-side (token, status, timestamps).
 */

export type QRCodeStatus = "active" | "revoked"

export interface QRCode {
  id: string
  tenantId: string
  branchId: string
  tableId: string
  token: string
  status: QRCodeStatus
  createdAt: string
}
