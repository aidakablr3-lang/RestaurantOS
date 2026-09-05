import { apiClient } from "@/lib/api-client"
import type {
  CommitMenuImportResult,
  MenuImportCommitRow,
  MenuImportExtractResult,
} from "@/types/menu-import"

const BASE = (restaurantId: string) => `/api/v1/restaurants/${restaurantId}/menu-imports`

// A multi-image vision extraction call routinely takes longer than the
// 15s default request timeout -- this is the one call in the app that
// needs real headroom.
const EXTRACT_TIMEOUT_MS = 120_000

export function extractMenuImport(restaurantId: string, files: File[]) {
  const body = new FormData()
  for (const file of files) {
    body.append("files", file)
  }
  return apiClient.postForm<MenuImportExtractResult>(`${BASE(restaurantId)}/extract`, body, {
    timeoutMs: EXTRACT_TIMEOUT_MS,
  })
}

export function commitMenuImport(
  restaurantId: string,
  rows: MenuImportCommitRow[],
  idempotencyKey: string
) {
  return apiClient.post<CommitMenuImportResult>(
    `${BASE(restaurantId)}/commit`,
    { rows },
    { idempotencyKey }
  )
}
