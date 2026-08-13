import { apiClient } from "@/lib/api-client"
import type { QRCode } from "@/types/qr-code"

// Also deliberately flat, same reasoning as changeTableStatus above --
// mirrors POST/GET /api/v1/tables/{id}/qr-codes exactly.
export function listQRCodes(tableId: string) {
  return apiClient.get<QRCode[]>(`/api/v1/tables/${tableId}/qr-codes`)
}

export function generateQRCode(tableId: string, idempotencyKey: string) {
  return apiClient.post<QRCode>(`/api/v1/tables/${tableId}/qr-codes`, undefined, {
    idempotencyKey,
  })
}
