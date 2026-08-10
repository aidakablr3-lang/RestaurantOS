import { z } from "zod"

export const reservationSchema = z.object({
  partySize: z.coerce
    .number()
    .int("Party size must be a whole number.")
    .gt(0, "Party size must be greater than zero."),
  requestedAt: z.string().min(1, "Choose a date and time."),
  tableId: z.string().optional(),
})

export type ReservationFormValues = z.infer<typeof reservationSchema>
