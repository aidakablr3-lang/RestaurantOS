import { apiClient } from "@/lib/api-client"
import type { CreateDiscountRequest, Discount, ListDiscountsParams } from "@/types/discount"

const BASE = "/api/v1/discounts"

export function listDiscounts(params: ListDiscountsParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<Discount[]>(`${BASE}?${search.toString()}`)
}

export function createDiscount(body: CreateDiscountRequest) {
  return apiClient.post<Discount>(BASE, body)
}
