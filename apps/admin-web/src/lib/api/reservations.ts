import { apiClient } from "@/lib/api-client"
import type {
  CreateReservationRequest,
  ListReservationsParams,
  Reservation,
  UpdateReservationRequest,
} from "@/types/reservation"

const BASE = (branchId: string) => `/api/v1/branches/${branchId}/reservations`

export function listReservations(branchId: string, params: ListReservationsParams) {
  const search = new URLSearchParams()
  search.set("offset", String(params.offset ?? 0))
  search.set("limit", String(params.limit ?? 20))
  return apiClient.get<Reservation[]>(`${BASE(branchId)}?${search.toString()}`)
}

export function getReservation(branchId: string, reservationId: string) {
  return apiClient.get<Reservation>(`${BASE(branchId)}/${reservationId}`)
}

export function createReservation(
  branchId: string,
  body: CreateReservationRequest,
  idempotencyKey: string
) {
  return apiClient.post<Reservation>(BASE(branchId), body, { idempotencyKey })
}

export function updateReservation(
  branchId: string,
  reservationId: string,
  body: UpdateReservationRequest
) {
  return apiClient.patch<Reservation>(`${BASE(branchId)}/${reservationId}`, body)
}
