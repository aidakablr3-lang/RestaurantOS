import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createReservation,
  listReservations,
  updateReservation,
} from "@/lib/api/reservations"
import type {
  CreateReservationRequest,
  ListReservationsParams,
  UpdateReservationRequest,
} from "@/types/reservation"

export const reservationKeys = {
  all: ["reservations"] as const,
  lists: (branchId: string) => [...reservationKeys.all, "list", branchId] as const,
  list: (branchId: string, params: ListReservationsParams) =>
    [...reservationKeys.lists(branchId), params] as const,
}

export function useReservations(
  branchId: string,
  params: ListReservationsParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: reservationKeys.list(branchId, params),
    queryFn: () => listReservations(branchId, params),
    enabled: options?.enabled,
  })
}

export function useCreateReservation(branchId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateReservationRequest
      idempotencyKey: string
    }) => createReservation(branchId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: reservationKeys.lists(branchId) })
    },
  })
}

// Used both for plain field edits (resubmit the reservation's own
// current status) and for status-transition quick actions (resubmit
// the current partySize/tableId, change only status) -- the backend
// treats a target equal to the current status as "no transition
// requested," so the same mutation covers both cases.
export function useUpdateReservation(branchId: string, reservationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateReservationRequest) =>
      updateReservation(branchId, reservationId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: reservationKeys.lists(branchId) })
    },
  })
}
