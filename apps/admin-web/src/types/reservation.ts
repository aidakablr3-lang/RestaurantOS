/**
 * Mirrors modules/restaurant/presentation/api/v1/reservation_router.py's
 * ReservationResponseSchema / Create·Update ReservationRequestSchema and
 * the domain's ReservationStatus StrEnum. Field names are camelCase on
 * the wire.
 *
 * ``customerId`` is always null -- no ``Customer`` entity exists
 * anywhere in this codebase yet (Architecture SS3.1); every
 * reservation is an anonymous guest/walk-in row. Never settable from
 * any request schema, only ever read back as null.
 */

export type ReservationStatus =
  | "requested"
  | "confirmed"
  | "seated"
  | "completed"
  | "no_show"
  | "canceled"

export interface Reservation {
  id: string
  tenantId: string
  branchId: string
  tableId: string | null
  customerId: string | null
  partySize: number
  requestedAt: string
  status: ReservationStatus
  createdAt: string
}

export interface CreateReservationRequest {
  partySize: number
  requestedAt: string
  tableId?: string | null
}

// ``status`` is present here unlike Table's UpdateTableRequest --
// Reservation has no separate flat status-change route, so PATCH alone
// carries both plain field edits and status transitions. Submitting the
// reservation's own current status alongside changed partySize/tableId
// is a plain edit; submitting a different status is a transition
// attempt the backend's own domain graph validates.
export interface UpdateReservationRequest {
  partySize: number
  status: ReservationStatus
  tableId?: string | null
}

export interface ListReservationsParams {
  offset?: number
  limit?: number
}
