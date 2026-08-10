import { apiClient } from "@/lib/api-client"
import type {
  Branch,
  BranchDetail,
  ListBranchesParams,
  OperatingHoursEntry,
  OperatingHoursEntryInput,
  UpdateBranchRequest,
} from "@/types/branch"

const BASE = "/api/v1/branches"

export function listBranches(params: ListBranchesParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<Branch[]>(`${BASE}?${search.toString()}`)
}

export function getBranch(branchId: string) {
  return apiClient.get<BranchDetail>(`${BASE}/${branchId}`)
}

export function updateBranch(branchId: string, body: UpdateBranchRequest) {
  return apiClient.patch<Branch>(`${BASE}/${branchId}`, body)
}

export function closeBranch(branchId: string, idempotencyKey: string) {
  return apiClient.post<Branch>(`${BASE}/${branchId}/close`, undefined, {
    idempotencyKey,
  })
}

export function reopenBranch(branchId: string, idempotencyKey: string) {
  return apiClient.post<Branch>(`${BASE}/${branchId}/reopen`, undefined, {
    idempotencyKey,
  })
}

export function replaceOperatingHours(
  branchId: string,
  entries: OperatingHoursEntryInput[],
  idempotencyKey: string
) {
  return apiClient.put<OperatingHoursEntry[]>(
    `${BASE}/${branchId}/operating-hours`,
    { entries },
    { idempotencyKey }
  )
}
