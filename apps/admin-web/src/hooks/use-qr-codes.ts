import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { generateQRCode, listQRCodes } from "@/lib/api/qr-codes"

export const qrCodeKeys = {
  all: ["qr-codes"] as const,
  list: (tableId: string) => [...qrCodeKeys.all, "list", tableId] as const,
}

export function useQRCodes(tableId: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: qrCodeKeys.list(tableId ?? ""),
    queryFn: () => listQRCodes(tableId as string),
    enabled: Boolean(tableId) && (options?.enabled ?? true),
  })
}

export function useGenerateQRCode(tableId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (idempotencyKey: string) => generateQRCode(tableId, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qrCodeKeys.list(tableId) })
    },
  })
}
