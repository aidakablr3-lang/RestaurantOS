import { apiClient } from "@/lib/api-client"
import type {
  CreateSupplierRequest,
  ListSuppliersParams,
  Supplier,
  UpdateSupplierRequest,
} from "@/types/supplier"

const BASE = "/api/v1/suppliers"

export function listSuppliers(params: ListSuppliersParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<Supplier[]>(`${BASE}?${search.toString()}`)
}

export function createSupplier(body: CreateSupplierRequest) {
  return apiClient.post<Supplier>(BASE, body)
}

export function updateSupplier(supplierId: string, body: UpdateSupplierRequest) {
  return apiClient.patch<Supplier>(`${BASE}/${supplierId}`, body)
}
